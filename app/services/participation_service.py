from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime

from app.core.database import Participant, User
from app.core.redis import cache

class ParticipationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_participant(self, contest_id: int, user_id: int, referrer_id: Optional[int] = None) -> Optional[Participant]:
        existing = await self.db.execute(
            select(Participant).where(
                and_(
                    Participant.contest_id == contest_id,
                    Participant.user_id == user_id
                )
            )
        )
        
        if existing.scalar_one_or_none():
            return None
        
        participant = Participant(
            contest_id=contest_id,
            user_id=user_id,
            referrer_id=referrer_id
        )
        
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        
        await cache.delete(f"participants_count:{contest_id}")
        await cache.delete(f"contest:{contest_id}")
        await cache.delete(f"user_participations:{user_id}")
        
        return participant
    
    async def is_participating(self, contest_id: int, user_id: int) -> bool:
        cache_key = f"participation:{contest_id}:{user_id}"
        cached_result = await cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        result = await self.db.execute(
            select(Participant).where(
                and_(
                    Participant.contest_id == contest_id,
                    Participant.user_id == user_id
                )
            )
        )
        is_participating = result.scalar_one_or_none() is not None
        
        await cache.set(cache_key, is_participating, 1800)
        return is_participating
    
    async def get_participants_count(self, contest_id: int) -> int:
        cache_key = f"participants_count:{contest_id}"
        cached_count = await cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        result = await self.db.execute(
            select(func.count(Participant.id)).where(
                Participant.contest_id == contest_id
            )
        )
        count = result.scalar() or 0
        
        await cache.set(cache_key, count, 300)
        return count
    
    async def get_participants(self, contest_id: int, limit: int = 1000) -> List[User]:
        result = await self.db.execute(
            select(User)
            .join(Participant)
            .where(Participant.contest_id == contest_id)
            .order_by(Participant.joined_at)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_recent_participants(self, contest_id: int, limit: int = 10) -> List[User]:
        result = await self.db.execute(
            select(User)
            .join(Participant)
            .where(Participant.contest_id == contest_id)
            .order_by(desc(Participant.joined_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def remove_participant(self, contest_id: int, user_id: int):
        result = await self.db.execute(
            select(Participant).where(
                and_(
                    Participant.contest_id == contest_id,
                    Participant.user_id == user_id
                )
            )
        )
        participant = result.scalar_one_or_none()
        
        if participant:
            await self.db.delete(participant)
            await self.db.commit()
            
            await cache.delete(f"participants_count:{contest_id}")
            await cache.delete(f"participation:{contest_id}:{user_id}")
            await cache.delete(f"contest:{contest_id}")
            await cache.delete(f"user_participations:{user_id}")
    
    async def get_user_participations(self, user_id: int) -> List[Participant]:
        cache_key = f"user_participations:{user_id}"
        cached_participations = await cache.get(cache_key)
        
        if cached_participations:
            return cached_participations
        
        result = await self.db.execute(
            select(Participant)
            .where(Participant.user_id == user_id)
            .order_by(desc(Participant.joined_at))
        )
        participations = list(result.scalars().all())
        
        await cache.set(cache_key, participations, 1800)
        return participations
    
    async def get_participation_stats(self, contest_id: int) -> dict:
        total_participants = await self.get_participants_count(contest_id)
        
        today = datetime.utcnow().date()
        today_participants = await self.db.execute(
            select(func.count(Participant.id)).where(
                and_(
                    Participant.contest_id == contest_id,
                    func.date(Participant.joined_at) == today
                )
            )
        )
        
        return {
            "total_participants": total_participants,
            "today_participants": today_participants.scalar() or 0
        }
