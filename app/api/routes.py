from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.core.database import get_db, User, Contest, Participant
from app.core.config import settings

router = APIRouter()
admin_router = APIRouter()
analytics_router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0", "timestamp": datetime.utcnow()}

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
                "participants": participants_count or 0,
                "timestamp": datetime.utcnow()
            }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@admin_router.get("/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    try:
        async with db as session:
            total_users = await session.scalar(select(func.count(User.id)))
            active_users = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )
            premium_users = await session.scalar(
                select(func.count(User.id)).where(User.is_premium == True)
            )
            total_contests = await session.scalar(select(func.count(Contest.id)))
            active_contests = await session.scalar(
                select(func.count(Contest.id)).where(Contest.status == "active")
            )
            
            return {
                "status": "success",
                "data": {
                    "total_users": total_users or 0,
                    "active_users": active_users or 0,
                    "premium_users": premium_users or 0,
                    "total_contests": total_contests or 0,
                    "active_contests": active_contests or 0
                },
                "timestamp": datetime.utcnow()
            }
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/overview")
async def get_analytics_overview(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    try:
        async with db as session:
            total_users = await session.scalar(select(func.count(User.id)))
            total_contests = await session.scalar(select(func.count(Contest.id)))
            total_participants = await session.scalar(select(func.count(Participant.id)))
            
            return {
                "status": "success",
                "data": {
                    "total_users": total_users or 0,
                    "total_contests": total_contests or 0,
                    "total_participants": total_participants or 0,
                    "period_days": days
                },
                "timestamp": datetime.utcnow()
            }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
