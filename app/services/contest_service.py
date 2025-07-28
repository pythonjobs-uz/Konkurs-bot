from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional, List

from app.core.database import Contest, Participant, User, Channel
from app.core.redis import cache

class ContestService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_contest(
        self,
        owner_id: int,
        channel_id: int,
        title: str,
        description: str,
        image_file_id: Optional[str] = None,
        participate_button_text: str = "🤝 Qatnashish",
        winners_count: int = 1,
        start_time: datetime = None,
        end_time: Optional[datetime] = None,
        max_participants: Optional[int] = None,
        prize_description: Optional[str] = None
    ) -> Contest:
        contest = Contest(
            owner_id=owner_id,
            channel_id=channel_id,
            title=title,
            description=description,
            image_file_id=image_file_id,
            participate_button_text=participate_button_text,
            winners_count=winners_count,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time,
            max_participants=max_participants,
            prize_description=prize_description
        )
        
        self.db.add(contest)
        await self.db.commit()
        await self.db.refresh(contest)
        
        await cache.delete("contest_statistics")
        await cache.delete("active_contests")
        
        return contest
    
    async def get_contest(self, contest_id: int) -> Optional[Contest]:
        cache_key = f"contest:{contest_id}"
        cached_contest = await cache.get(cache_key)
        
        if cached_contest:
            return cached_contest
        
        result = await self.db.execute(
            select(Contest)
            .options(
                selectinload(Contest.owner),
                selectinload(Contest.channel)
            )
            .where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            await cache.set(cache_key, contest, 1800)
        
        return contest
    
    async def get_user_contests(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Contest]:
        result = await self.db.execute(
            select(Contest)
            .where(Contest.owner_id == user_id)
            .order_by(desc(Contest.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_user_contests_count(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Contest.id)).where(Contest.owner_id == user_id)
        )
        return result.scalar() or 0
    
    async def get_active_contests(self) -> List[Contest]:
        cache_key = "active_contests"
        cached_contests = await cache.get(cache_key)
        
        if cached_contests:
            return cached_contests
        
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Contest)
            .where(
                and_(
                    Contest.status.in_(["pending", "active"]),
                    Contest.start_time <= now
                )
            )
        )
        contests = list(result.scalars().all())
        
        await cache.set(cache_key, contests, 300)
        return contests
    
    async def get_contests_by_status(self, status: str, limit: int = 50) -> List[Contest]:
        result = await self.db.execute(
            select(Contest)
            .where(Contest.status == status)
            .order_by(desc(Contest.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_recent_contests(self, limit: int = 50) -> List[Contest]:
        result = await self.db.execute(
            select(Contest)
            .order_by(desc(Contest.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def update_contest_status(self, contest_id: int, status: str):
        result = await self.db.execute(
            select(Contest).where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            contest.status = status
            contest.updated_at = datetime.utcnow()
            await self.db.commit()
            
            await cache.delete(f"contest:{contest_id}")
            await cache.delete("active_contests")
            await cache.delete("contest_statistics")
    
    async def set_contest_message_id(self, contest_id: int, message_id: int):
        result = await self.db.execute(
            select(Contest).where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            contest.message_id = message_id
            await self.db.commit()
            
            await cache.delete(f"contest:{contest_id}")
    
    async def increment_view_count(self, contest_id: int):
        result = await self.db.execute(
            select(Contest).where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            contest.view_count += 1
            await self.db.commit()
            
            await cache.delete(f"contest:{contest_id}")
    
    async def update_participant_count(self, contest_id: int):
        participant_count = await self.db.execute(
            select(func.count(Participant.id)).where(Participant.contest_id == contest_id)
        )
        count = participant_count.scalar() or 0
        
        result = await self.db.execute(
            select(Contest).where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            contest.participant_count = count
            await self.db.commit()
            
            await cache.delete(f"contest:{contest_id}")
    
    async def get_trending_contests(self, limit: int = 10) -> List[Contest]:
        result = await self.db.execute(
            select(Contest)
            .where(Contest.status == "active")
            .order_by(desc(Contest.view_count))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def search_contests(self, query: str, limit: int = 20) -> List[Contest]:
        search_pattern = f"%{query}%"
        result = await self.db.execute(
            select(Contest)
            .where(
                and_(
                    Contest.status.in_(["active", "pending"]),
                    or_(
                        Contest.title.ilike(search_pattern),
                        Contest.description.ilike(search_pattern)
                    )
                )
            )
            .order_by(desc(Contest.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def delete_contest(self, contest_id: int) -> bool:
        result = await self.db.execute(
            select(Contest).where(Contest.id == contest_id)
        )
        contest = result.scalar_one_or_none()
        
        if contest:
            await self.db.delete(contest)
            await self.db.commit()
            
            await cache.delete(f"contest:{contest_id}")
            await cache.delete("active_contests")
            await cache.delete("contest_statistics")
            return True
        
        return False
