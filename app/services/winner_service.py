from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
import random
from datetime import datetime

from app.core.database import Winner, User, Participant, Contest
from app.core.redis import cache

class WinnerService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def select_winners(self, contest_id: int, winners_count: int) -> List[User]:
        cache_key = f"contest_winners:{contest_id}"
        cached_winners = await cache.get(cache_key)
        
        if cached_winners:
            return cached_winners
        
        result = await self.db.execute(
            select(User)
            .join(Participant)
            .where(Participant.contest_id == contest_id)
        )
        participants = result.scalars().all()
        
        if not participants:
            return []
        
        winners_count = min(winners_count, len(participants))
        selected_winners = random.sample(participants, winners_count)
        
        existing_winners = await self.db.execute(
            select(Winner).where(Winner.contest_id == contest_id)
        )
        
        if existing_winners.scalars().first():
            return selected_winners
        
        for position, winner in enumerate(selected_winners, 1):
            winner_record = Winner(
                contest_id=contest_id,
                user_id=winner.id,
                position=position
            )
            self.db.add(winner_record)
        
        await self.db.commit()
        
        await cache.set(cache_key, selected_winners, 3600)
        return selected_winners
    
    async def get_contest_winners(self, contest_id: int) -> List[User]:
        cache_key = f"contest_winners:{contest_id}"
        cached_winners = await cache.get(cache_key)
        
        if cached_winners:
            return cached_winners
        
        result = await self.db.execute(
            select(User)
            .join(Winner)
            .where(Winner.contest_id == contest_id)
            .order_by(Winner.position)
        )
        winners = result.scalars().all()
        
        if winners:
            await cache.set(cache_key, winners, 3600)
        
        return winners
    
    async def mark_prize_claimed(self, contest_id: int, user_id: int):
        result = await self.db.execute(
            select(Winner).where(
                and_(
                    Winner.contest_id == contest_id,
                    Winner.user_id == user_id
                )
            )
        )
        winner = result.scalar_one_or_none()
        
        if winner:
            winner.prize_claimed = True
            await self.db.commit()
            
            await cache.delete(f"contest_winners:{contest_id}")
    
    async def get_user_wins(self, user_id: int) -> List[Winner]:
        result = await self.db.execute(
            select(Winner)
            .where(Winner.user_id == user_id)
            .order_by(Winner.announced_at.desc())
        )
        return result.scalars().all()
    
    async def get_winner_statistics(self, user_id: int) -> dict:
        total_wins = await self.db.execute(
            select(func.count(Winner.id)).where(Winner.user_id == user_id)
        )
        
        first_place_wins = await self.db.execute(
            select(func.count(Winner.id)).where(
                and_(Winner.user_id == user_id, Winner.position == 1)
            )
        )
        
        claimed_prizes = await self.db.execute(
            select(func.count(Winner.id)).where(
                and_(Winner.user_id == user_id, Winner.prize_claimed == True)
            )
        )
        
        return {
            "total_wins": total_wins.scalar() or 0,
            "first_place_wins": first_place_wins.scalar() or 0,
            "claimed_prizes": claimed_prizes.scalar() or 0
        }
