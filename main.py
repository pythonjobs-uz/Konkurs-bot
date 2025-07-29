from fastapi import FastAPI, Request, HTTPException, Depends, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import uvicorn
import asyncio
from datetime import datetime, timedelta
import secrets
import hashlib
import hmac
import json

from db import get_db, init_db
from models import User, Contest, Participant, Winner, Admin
from bot import TelegramBot
from config import settings
from utils import verify_telegram_data, generate_token, hash_password, verify_password

bot = TelegramBot(settings.BOT_TOKEN)
security = HTTPBasic()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bot.set_webhook(f"{settings.WEBHOOK_URL}/webhook/{settings.BOT_TOKEN}")
    yield
    await bot.delete_webhook()

app = FastAPI(title="Contest Bot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_admin(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == credentials.username).first()
    if not admin or not verify_password(credentials.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return admin

@app.post(f"/webhook/{settings.BOT_TOKEN}")
async def webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        await bot.process_update(data, db)
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
async def admin_dashboard(request: Request, admin: Admin = Depends(verify_admin), db: Session = Depends(get_db)):
    stats = {
        "total_users": db.query(User).count(),
        "active_contests": db.query(Contest).filter(Contest.status == "active").count(),
        "total_contests": db.query(Contest).count(),
        "total_participants": db.query(Participant).count()
    }
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "stats": stats,
        "admin": admin
    })

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, admin: Admin = Depends(verify_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "users": users,
        "admin": admin
    })

@app.get("/admin/contests", response_class=HTMLResponse)
async def admin_contests(request: Request, admin: Admin = Depends(verify_admin), db: Session = Depends(get_db)):
    contests = db.query(Contest).order_by(Contest.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin_contests.html", {
        "request": request,
        "contests": contests,
        "admin": admin
    })

@app.post("/admin/broadcast")
async def admin_broadcast(
    message: str = Form(...),
    admin: Admin = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.is_active == True).all()
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
async def user_profile(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    contests = db.query(Contest).filter(Contest.owner_id == user.id).all()
    participations = db.query(Participant).filter(Participant.user_id == user.id).all()
    
    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "user": user,
        "contests": contests,
        "participations": participations
    })

@app.get("/contest/{contest_id}", response_class=HTMLResponse)
async def contest_view(request: Request, contest_id: int, db: Session = Depends(get_db)):
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    participants = db.query(Participant).filter(Participant.contest_id == contest_id).all()
    winners = db.query(Winner).filter(Winner.contest_id == contest_id).all()
    
    return templates.TemplateResponse("contest_view.html", {
        "request": request,
        "contest": contest,
        "participants": participants,
        "winners": winners
    })

@app.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "contests": db.query(Contest).count(),
        "active_contests": db.query(Contest).filter(Contest.status == "active").count(),
        "participants": db.query(Participant).count()
    }

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
