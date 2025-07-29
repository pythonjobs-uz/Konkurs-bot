from fastapi import FastAPI, Request, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import aiohttp
import json
import random
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
import os

from db import Database, get_db
from models import User, Contest, Participant, Winner, Admin, Settings
from config import settings

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
    
    async def send_message(self, chat_id: int, text: str, reply_markup=None):
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/sendMessage", json=data) as resp:
                return await resp.json()
    
    async def send_photo(self, chat_id: int, photo: str, caption: str = "", reply_markup=None):
        data = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/sendPhoto", json=data) as resp:
                return await resp.json()
    
    async def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup=None):
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/editMessageText", json=data) as resp:
                return await resp.json()
    
    async def set_webhook(self, url: str):
        data = {"url": url}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/setWebhook", json=data) as resp:
                return await resp.json()
    
    async def delete_webhook(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/deleteWebhook") as resp:
                return await resp.json()
    
    async def process_update(self, update: dict, db):
        try:
            if "message" in update:
                await self.handle_message(update["message"], db)
            elif "callback_query" in update:
                await self.handle_callback(update["callback_query"], db)
        except Exception as e:
            print(f"Error processing update: {e}")
    
    async def handle_message(self, message: dict, db):
        user_data = message["from"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        
        user = await self.get_or_create_user(user_data, db)
        
        if text == "/start":
            await self.send_start_message(chat_id, user)
        elif text == "/contests":
            await self.send_contests_list(chat_id, user, db)
        elif text == "/profile":
            await self.send_profile(chat_id, user, db)
        elif text == "/help":
            await self.send_help(chat_id)
        else:
            await self.send_message(chat_id, "Unknown command. Use /help for available commands.")
    
    async def handle_callback(self, callback: dict, db):
        user_data = callback["from"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        data = callback["data"]
        
        user = await self.get_or_create_user(user_data, db)
        
        if data.startswith("join_"):
            contest_id = int(data.split("_")[1])
            await self.join_contest(chat_id, message_id, contest_id, user, db)
        elif data.startswith("view_"):
            contest_id = int(data.split("_")[1])
            await self.view_contest(chat_id, contest_id, db)
        elif data == "my_contests":
            await self.send_user_contests(chat_id, user, db)
        elif data == "active_contests":
            await self.send_active_contests(chat_id, db)
    
    async def get_or_create_user(self, user_data: dict, db):
        user = await db.get_user_by_telegram_id(user_data["id"])
        if not user:
            user = User(
                telegram_id=user_data["id"],
                username=user_data.get("username"),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
                language_code=user_data.get("language_code", "en")
            )
            await db.create_user(user)
        return user
    
    async def send_start_message(self, chat_id: int, user: User):
        text = f"""🎉 <b>Welcome to Contest Bot!</b>

Hello {user.first_name}! 

🏆 Create and manage contests
👥 Join exciting contests
📊 Track your participation

<b>Quick Start:</b>
• /contests - View active contests
• /profile - Your profile
• /help - Get help

Ready to start? Choose an option below!"""
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🏆 Active Contests", "callback_data": "active_contests"}],
                [{"text": "📝 My Contests", "callback_data": "my_contests"}],
                [{"text": "ℹ️ Help", "callback_data": "help"}]
            ]
        }
        
        await self.send_message(chat_id, text, keyboard)
    
    async def send_contests_list(self, chat_id: int, user: User, db):
        contests = await db.get_active_contests(10)
        
        if not contests:
            await self.send_message(chat_id, "No active contests at the moment.")
            return
        
        text = "<b>🏆 Active Contests:</b>\n\n"
        keyboard = {"inline_keyboard": []}
        
        for contest in contests:
            participants_count = await db.get_participants_count(contest.id)
            text += f"🎯 <b>{contest.title}</b>\n"
            text += f"👥 {participants_count} participants\n"
            text += f"🏆 {contest.winners_count} winners\n\n"
            
            keyboard["inline_keyboard"].append([
                {"text": f"Join {contest.title}", "callback_data": f"join_{contest.id}"}
            ])
        
        await self.send_message(chat_id, text, keyboard)
    
    async def join_contest(self, chat_id: int, message_id: int, contest_id: int, user: User, db):
        contest = await db.get_contest(contest_id)
        if not contest or contest.status != "active":
            await self.send_message(chat_id, "Contest not found or not active.")
            return
        
        existing = await db.get_participant(contest_id, user.id)
        if existing:
            await self.send_message(chat_id, "You're already participating in this contest!")
            return
        
        if contest.max_participants:
            current_count = await db.get_participants_count(contest_id)
            if current_count >= contest.max_participants:
                await self.send_message(chat_id, "Contest is full!")
                return
        
        participant = Participant(contest_id=contest_id, user_id=user.id)
        await db.create_participant(participant)
        
        await self.send_message(chat_id, f"✅ Successfully joined '{contest.title}'! Good luck! 🍀")
        
        if contest.end_time and contest.end_time <= datetime.utcnow():
            await self.end_contest(contest, db)
    
    async def end_contest(self, contest: Contest, db):
        participants = await db.get_contest_participants(contest.id)
        
        if len(participants) < contest.winners_count:
            winners = participants
        else:
            winners = random.sample(participants, contest.winners_count)
        
        for i, participant in enumerate(winners):
            winner = Winner(
                contest_id=contest.id,
                user_id=participant.user_id,
                position=i + 1
            )
            await db.create_winner(winner)
            await db.update_participant_winner_status(participant.id, True)
        
        await db.update_contest_status(contest.id, "ended")
        
        for winner in winners:
            user = await db.get_user(winner.user_id)
            await self.send_message(
                user.telegram_id,
                f"🎉 Congratulations! You won '{contest.title}'! 🏆"
            )
    
    async def send_help(self, chat_id: int):
        text = """<b>🤖 Contest Bot Help</b>

<b>Commands:</b>
/start - Start the bot
/contests - View active contests
/profile - Your profile and stats
/help - Show this help

<b>Features:</b>
🏆 Create unlimited contests
👥 Join contests from other users
📊 Track your participation
🎯 Automatic winner selection
📱 Easy-to-use interface

<b>Support:</b>
Need help? Contact @support

<b>Terms:</b>
By using this bot, you agree to our Terms of Service and Privacy Policy."""
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📋 Terms of Service", "url": f"{settings.WEBHOOK_URL}/terms"}],
                [{"text": "🔒 Privacy Policy", "url": f"{settings.WEBHOOK_URL}/privacy"}]
            ]
        }
        
        await self.send_message(chat_id, text, keyboard)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + pwdhash.hex()

def verify_password(password: str, hash_str: str) -> bool:
    salt = hash_str[:32]
    stored_hash = hash_str[32:]
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return pwdhash.hex() == stored_hash

bot = TelegramBot(settings.BOT_TOKEN)
security = HTTPBasic()
db_instance = Database()

async def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    admin = await db_instance.get_admin_by_username(credentials.username)
    if not admin or not verify_password(credentials.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_instance.init_db()
    
    admin_exists = await db_instance.get_admin_by_username("admin")
    if not admin_exists:
        admin = Admin(
            username="admin",
            password_hash=hash_password("admin123")
        )
        await db_instance.create_admin(admin)
    
    try:
        await bot.set_webhook(f"{settings.WEBHOOK_URL}/webhook/{settings.BOT_TOKEN}")
    except:
        pass
    
    yield
    
    try:
        await bot.delete_webhook()
    except:
        pass
    
    await db_instance.close()

app = FastAPI(title="Contest Bot", lifespan=lifespan)

if not os.path.exists("static"):
    os.makedirs("static")
if not os.path.exists("templates"):
    os.makedirs("templates")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post(f"/webhook/{settings.BOT_TOKEN}")
async def webhook(request: Request):
    try:
        data = await request.json()
        await bot.process_update(data, db_instance)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: Admin = Depends(verify_admin)):
    stats = {
        "total_users": await db_instance.get_users_count(),
        "active_contests": await db_instance.get_active_contests_count(),
        "total_contests": await db_instance.get_contests_count(),
        "total_participants": await db_instance.get_participants_count()
    }
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "stats": stats,
        "admin": admin
    })

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, admin: Admin = Depends(verify_admin)):
    users = await db_instance.get_recent_users(100)
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "users": users,
        "admin": admin
    })

@app.get("/admin/contests", response_class=HTMLResponse)
async def admin_contests(request: Request, admin: Admin = Depends(verify_admin)):
    contests = await db_instance.get_recent_contests(100)
    return templates.TemplateResponse("admin_contests.html", {
        "request": request,
        "contests": contests,
        "admin": admin
    })

@app.post("/admin/broadcast")
async def admin_broadcast(message: str = Form(...), admin: Admin = Depends(verify_admin)):
    users = await db_instance.get_active_users()
    success_count = 0
    
    for user in users:
        try:
            await bot.send_message(user.telegram_id, message)
            success_count += 1
            await asyncio.sleep(0.05)
        except:
            continue
    
    return {"success": True, "sent_count": success_count}

@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_profile(request: Request, user_id: int):
    user = await db_instance.get_user_by_telegram_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    contests = await db_instance.get_user_contests(user.id)
    participations = await db_instance.get_user_participations(user.id)
    
    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "user": user,
        "contests": contests,
        "participations": participations
    })

@app.get("/contest/{contest_id}", response_class=HTMLResponse)
async def contest_view(request: Request, contest_id: int):
    contest = await db_instance.get_contest(contest_id)
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    participants = await db_instance.get_contest_participants(contest_id)
    winners = await db_instance.get_contest_winners(contest_id)
    
    return templates.TemplateResponse("contest_view.html", {
        "request": request,
        "contest": contest,
        "participants": participants,
        "winners": winners
    })

@app.get("/api/stats")
async def api_stats():
    return {
        "users": await db_instance.get_users_count(),
        "contests": await db_instance.get_contests_count(),
        "active_contests": await db_instance.get_active_contests_count(),
        "participants": await db_instance.get_participants_count()
    }

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
