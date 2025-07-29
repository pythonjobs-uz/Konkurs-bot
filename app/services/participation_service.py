from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from datetime import datetime

from app.core.database import Participant, User
from app.core.redis import redis_manager

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
        
        await redis_manager.delete(f"participants_count:{contest_id}")
        await redis_manager.delete(f"contest:{contest_id}")
        await redis_manager.delete(f"participation:{contest_id}:{user_id}")
        
        return participant
    
    async def is_participating(self, contest_id: int, user_id: int) -> bool:
        cached_result = await redis_manager.get(f"participation:{contest_id}:{user_id}")
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
        
        await redis_manager.set(f"participation:{contest_id}:{user_id}", is_participating, 1800)
        return is_participating
    
    async def get_participants_count(self, contest_id: int) -> int:
        cached_count = await redis_manager.get(f"participants_count:{contest_id}")
        if cached_count is not None:
            return cached_count
        
        result = await self.db.execute(
            select(func.count(Participant.id)).where(
                Participant.contest_id == contest_id
            )
        )
        count = result.scalar() or 0
        
        await redis_manager.set(f"participants_count:{contest_id}", count, 300)
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
