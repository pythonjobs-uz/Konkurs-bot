from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from app.core.database import User, Contest, Participant
from app.core.redis import cache

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_or_update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = "uz"
    ) -> User:
        cache_key = f"user:{user_id}"
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.language_code = language_code
            user.last_activity = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code
            )
            self.db.add(user)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        await cache.set(cache_key, user, 3600)
        return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        cache_key = f"user:{user_id}"
        cached_user = await cache.get(cache_key)
        
        if cached_user:
            return cached_user
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            await cache.set(cache_key, user, 3600)
        
        return user
    
    async def get_all_active_users(self) -> List[User]:
        result = await self.db.execute(
            select(User).where(User.is_active == True)
        )
        return result.scalars().all()
    
    async def get_premium_users(self) -> List[User]:
        result = await self.db.execute(
            select(User).where(
                and_(User.is_active == True, User.is_premium == True)
            )
        )
        return result.scalars().all()
    
    async def update_premium_status(self, user_id: int, is_premium: bool):
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_premium = is_premium
            await self.db.commit()
            
            cache_key = f"user:{user_id}"
            await cache.delete(cache_key)
    
    async def get_statistics(self) -> Dict[str, int]:
        cache_key = "user_statistics"
        cached_stats = await cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        total_users_result = await self.db.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar()
        
        active_users_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_result.scalar()
        
        premium_users_result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(User.is_active == True, User.is_premium == True)
            )
        )
        premium_users = premium_users_result.scalar()
        
        today = datetime.utcnow().date()
        new_today_result = await self.db.execute(
            select(func.count(User.id)).where(
                func.date(User.created_at) == today
            )
        )
        new_today = new_today_result.scalar()
        
        total_contests_result = await self.db.execute(
            select(func.count(Contest.id))
        )
        total_contests = total_contests_result.scalar()
        
        active_contests_result = await self.db.execute(
            select(func.count(Contest.id)).where(Contest.status == "active")
        )
        active_contests = active_contests_result.scalar()
        
        stats = {
            "total_users": total_users,
            "active_users": active_users,
            "premium_users": premium_users,
            "new_today": new_today,
            "total_contests": total_contests,
            "active_contests": active_contests
        }
        
        await cache.set(cache_key, stats, 300)
        return stats
    
    async def get_user_activity_stats(self, days: int = 7) -> Dict[str, int]:
        since_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(func.count(User.id)).where(
                User.last_activity >= since_date
            )
        )
        
        return {"active_users": result.scalar()}
