import aiohttp
import json
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import User, Contest, Participant, Winner
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
    
    async def process_update(self, update: dict, db: Session):
        if "message" in update:
            await self.handle_message(update["message"], db)
        elif "callback_query" in update:
            await self.handle_callback(update["callback_query"], db)
    
    async def handle_message(self, message: dict, db: Session):
        user_data = message["from"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        
        user = self.get_or_create_user(user_data, db)
        
        if text == "/start":
            await self.send_start_message(chat_id, user)
        elif text == "/contests":
            await self.send_contests_list(chat_id, user, db)
        elif text == "/create":
            await self.send_create_contest_form(chat_id, user)
        elif text == "/profile":
            await self.send_profile(chat_id, user, db)
        elif text == "/help":
            await self.send_help(chat_id)
        else:
            await self.send_message(chat_id, "Unknown command. Use /help for available commands.")
    
    async def handle_callback(self, callback: dict, db: Session):
        user_data = callback["from"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        data = callback["data"]
        
        user = self.get_or_create_user(user_data, db)
        
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
    
    def get_or_create_user(self, user_data: dict, db: Session) -> User:
        user = db.query(User).filter(User.telegram_id == user_data["id"]).first()
        if not user:
            user = User(
                telegram_id=user_data["id"],
                username=user_data.get("username"),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
                language_code=user_data.get("language_code", "en")
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    
    async def send_start_message(self, chat_id: int, user: User):
        text = f"""
🎉 <b>Welcome to Contest Bot!</b>

Hello {user.first_name}! 

🏆 Create and manage contests
👥 Join exciting contests
📊 Track your participation

<b>Quick Start:</b>
• /contests - View active contests
• /create - Create new contest
• /profile - Your profile
• /help - Get help

Ready to start? Choose an option below!
        """
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🏆 Active Contests", "callback_data": "active_contests"}],
                [{"text": "📝 My Contests", "callback_data": "my_contests"}],
                [{"text": "ℹ️ Help", "callback_data": "help"}]
            ]
        }
        
        await self.send_message(chat_id, text, keyboard)
    
    async def send_contests_list(self, chat_id: int, user: User, db: Session):
        contests = db.query(Contest).filter(Contest.status == "active").limit(10).all()
        
        if not contests:
            await self.send_message(chat_id, "No active contests at the moment.")
            return
        
        text = "<b>🏆 Active Contests:</b>\n\n"
        keyboard = {"inline_keyboard": []}
        
        for contest in contests:
            participants_count = db.query(Participant).filter(Participant.contest_id == contest.id).count()
            text += f"🎯 <b>{contest.title}</b>\n"
            text += f"👥 {participants_count} participants\n"
            text += f"🏆 {contest.winners_count} winners\n\n"
            
            keyboard["inline_keyboard"].append([
                {"text": f"Join {contest.title}", "callback_data": f"join_{contest.id}"}
            ])
        
        await self.send_message(chat_id, text, keyboard)
    
    async def join_contest(self, chat_id: int, message_id: int, contest_id: int, user: User, db: Session):
        contest = db.query(Contest).filter(Contest.id == contest_id).first()
        if not contest or contest.status != "active":
            await self.send_message(chat_id, "Contest not found or not active.")
            return
        
        existing = db.query(Participant).filter(
            Participant.contest_id == contest_id,
            Participant.user_id == user.id
        ).first()
        
        if existing:
            await self.send_message(chat_id, "You're already participating in this contest!")
            return
        
        if contest.max_participants:
            current_count = db.query(Participant).filter(Participant.contest_id == contest_id).count()
            if current_count >= contest.max_participants:
                await self.send_message(chat_id, "Contest is full!")
                return
        
        participant = Participant(contest_id=contest_id, user_id=user.id)
        db.add(participant)
        db.commit()
        
        await self.send_message(chat_id, f"✅ Successfully joined '{contest.title}'! Good luck! 🍀")
        
        if contest.end_time and contest.end_time <= datetime.utcnow():
            await self.end_contest(contest, db)
    
    async def end_contest(self, contest: Contest, db: Session):
        participants = db.query(Participant).filter(Participant.contest_id == contest.id).all()
        
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
            db.add(winner)
            participant.is_winner = True
        
        contest.status = "ended"
        db.commit()
        
        for winner in winners:
            user = db.query(User).filter(User.id == winner.user_id).first()
            await self.send_message(
                user.telegram_id,
                f"🎉 Congratulations! You won '{contest.title}'! 🏆"
            )
    
    async def send_help(self, chat_id: int):
        text = """
<b>🤖 Contest Bot Help</b>

<b>Commands:</b>
/start - Start the bot
/contests - View active contests
/create - Create new contest
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
By using this bot, you agree to our Terms of Service and Privacy Policy.
        """
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📋 Terms of Service", "url": f"{settings.WEBHOOK_URL}/terms"}],
                [{"text": "🔒 Privacy Policy", "url": f"{settings.WEBHOOK_URL}/privacy"}]
            ]
        }
        
        await self.send_message(chat_id, text, keyboard)
