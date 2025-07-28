from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.core.database import get_db, User, Contest, Participant
from app.services.user_service import UserService
from app.services.contest_service import ContestService
from app.services.analytics_service import AnalyticsService
from app.core.config import settings

admin_router = APIRouter()
webhook_router = APIRouter()
analytics_router = APIRouter()
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

@admin_router.get("/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    analytics_service = AnalyticsService(db)
    stats = await analytics_service.get_system_analytics()
    
    return {
        "status": "success",
        "data": stats,
        "timestamp": datetime.utcnow().isoformat()
    }

@admin_router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    premium_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    user_service = UserService(db)
    
    if premium_only:
        users = await user_service.get_premium_users()
    else:
        users = await user_service.get_all_active_users()
    
    if search:
        users = [u for u in users if search.lower() in (u.username or "").lower() or search.lower() in (u.first_name or "").lower()]
    
    start = (page - 1) * limit
    end = start + limit
    paginated_users = users[start:end]
    
    return {
        "status": "success",
        "data": {
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code,
                    "is_premium": user.is_premium,
                    "last_activity": user.last_activity.isoformat() if user.last_activity else None,
                    "created_at": user.created_at.isoformat()
                }
                for user in paginated_users
            ],
            "total": len(users),
            "page": page,
            "limit": limit,
            "total_pages": (len(users) + limit - 1) // limit
        }
    }

@admin_router.get("/contests")
async def get_contests(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    contest_service = ContestService(db)
    
    if status:
        contests = await contest_service.get_contests_by_status(status, limit)
    else:
        contests = await contest_service.get_recent_contests(limit)
    
    return {
        "status": "success",
        "data": [
            {
                "id": contest.id,
                "title": contest.title,
                "status": contest.status,
                "owner_id": contest.owner_id,
                "participants_count": len(contest.participants) if contest.participants else 0,
                "winners_count": contest.winners_count,
                "start_time": contest.start_time.isoformat(),
                "end_time": contest.end_time.isoformat() if contest.end_time else None,
                "view_count": contest.view_count,
                "created_at": contest.created_at.isoformat()
            }
            for contest in contests
        ]
    }

@admin_router.post("/broadcast")
async def create_broadcast(
    message_text: str,
    target_users: Optional[List[int]] = None,
    premium_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    from app.services.broadcast_service import BroadcastService
    
    broadcast_service = BroadcastService(db)
    
    if premium_only:
        user_service = UserService(db)
        premium_users = await user_service.get_premium_users()
        target_users = [user.id for user in premium_users]
    
    success_count = await broadcast_service.send_advanced_broadcast(
        admin_id=0,
        message_text=message_text,
        target_users=target_users
    )
    
    return {
        "status": "success",
        "message": "Broadcast sent successfully",
        "sent_count": success_count
    }

@analytics_router.get("/overview")
async def get_analytics_overview(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    analytics_service = AnalyticsService(db)
    
    system_stats = await analytics_service.get_system_analytics()
    popular_contests = await analytics_service.get_popular_contests(10)
    
    return {
        "status": "success",
        "data": {
            "system_stats": system_stats,
            "popular_contests": [
                {
                    "id": contest.id,
                    "title": contest.title,
                    "participants": len(contest.participants) if contest.participants else 0,
                    "views": contest.view_count
                }
                for contest in popular_contests
            ],
            "period_days": days
        }
    }

@analytics_router.get("/contest/{contest_id}")
async def get_contest_analytics(
    contest_id: int,
    db: AsyncSession = Depends(get_db)
):
    analytics_service = AnalyticsService(db)
    contest_service = ContestService(db)
    
    contest = await contest_service.get_contest(contest_id)
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    analytics = await analytics_service.get_contest_analytics(contest_id)
    engagement = await analytics_service.get_engagement_metrics(contest_id)
    
    return {
        "status": "success",
        "data": {
            "contest": {
                "id": contest.id,
                "title": contest.title,
                "status": contest.status
            },
            "analytics": analytics,
            "engagement": engagement
        }
    }

@analytics_router.get("/user/{user_id}")
async def get_user_analytics(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    analytics_service = AnalyticsService(db)
    user_service = UserService(db)
    
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    analytics = await analytics_service.get_user_analytics(user_id)
    
    return {
        "status": "success",
        "data": {
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_premium": user.is_premium
            },
            "analytics": analytics
        }
    }

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    try:
        async with db as session:
            users_count = await session.scalar(select(func.count(User.id)))
            contests_count = await session.scalar(select(func.count(Contest.id)))
            participants_count = await session.scalar(select(func.count(Participant.id)))
            
            return {
                "users": users_count or 0,
                "contests": contests_count or 0,
                "participants": participants_count or 0
            }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@webhook_router.post("/telegram")
async def telegram_webhook():
    return {"status": "ok"}

@router.post("/webhook")
async def webhook_handler(request: Request):
    if not settings.USE_WEBHOOK:
        raise HTTPException(status_code=404, detail="Webhook not enabled")
    
    try:
        secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_token != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret token")
        
        update_data = await request.json()
        
        if hasattr(request.app.state, 'dp') and hasattr(request.app.state, 'bot'):
            await request.app.state.dp.feed_update(
                request.app.state.bot, 
                update_data
            )
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
