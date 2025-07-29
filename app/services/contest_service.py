import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.core.database import db
from app.core.redis import cache
import logging

logger = logging.getLogger(__name__)

class ContestService:
    @staticmethod
    async def create_contest(
        owner_id: int,
        channel_id: int,
        title: str,
        description: str,
        image_file_id: str = None,
        participate_button_text: str = "🤝 Qatnashish",
        winners_count: int = 1,
        start_time: str = None,
        end_time: str = None,
        max_participants: int = None,
        prize_description: str = None,
        requirements: str = None
    ) -> int:
        contest_id = await db.create_contest(
            owner_id=owner_id,
            channel_id=channel_id,
            title=title,
            description=description,
            image_file_id=image_file_id,
            participate_button_text=participate_button_text,
            winners_count=winners_count,
            start_time=start_time,
            end_time=end_time,
            max_participants=max_participants,
            prize_description=prize_description,
            requirements=requirements
        )
        
        await cache.delete(f"user_contests:{owner_id}")
        await cache.delete("active_contests")
        
        return contest_id
    
    @staticmethod
    async def get_contest_with_cache(contest_id: int) -> Optional[Dict[str, Any]]:
        cache_key = f"contest:{contest_id}"
        contest = await cache.get(cache_key)
        
        if not contest:
            contest = await db.get_contest(contest_id)
            if contest:
                await cache.set(cache_key, contest, expire=300)
        
        return contest
    
    @staticmethod
    async def join_contest(contest_id: int, user_id: int, referral_source: str = None) -> bool:
        contest = await ContestService.get_contest_with_cache(contest_id)
        
        if not contest or contest['status'] != 'active':
            return False
        
        if contest['max_participants']:
            current_participants = await db.get_participants_count(contest_id)
            if current_participants >= contest['max_participants']:
                return False
        
        is_already_participating = await db.is_participating(contest_id, user_id)
        if is_already_participating:
            return False
        
        success = await db.add_participant(contest_id, user_id, referral_source)
        
        if success:
            await cache.delete(f"contest:{contest_id}")
            await cache.delete(f"contest_participants:{contest_id}")
        
        return success
    
    @staticmethod
    async def select_winners(contest_id: int) -> List[Dict[str, Any]]:
        contest = await db.get_contest(contest_id)
        if not contest:
            return []
        
        participants = await db.get_contest_participants(contest_id)
        if not participants:
            return []
        
        winners_count = min(contest['winners_count'], len(participants))
        selected_winners = random.sample(participants, winners_count)
        
        for i, winner in enumerate(selected_winners, 1):
            await db.create_winner(contest_id, winner['id'], i)
        
        await cache.delete(f"contest:{contest_id}")
        await cache.delete(f"contest_winners:{contest_id}")
        
        return selected_winners
    
    @staticmethod
    async def get_contest_statistics(contest_id: int) -> Dict[str, Any]:
        cache_key = f"contest_stats:{contest_id}"
        stats = await cache.get(cache_key)
        
        if not stats:
            contest = await db.get_contest(contest_id)
            if not contest:
                return {}
            
            participants_count = await db.get_participants_count(contest_id)
            winners = await db.get_contest_winners(contest_id)
            
            stats = {
                "contest": contest,
                "participants_count": participants_count,
                "winners_count": len(winners),
                "winners": winners,
                "status": contest['status'],
                "view_count": contest.get('view_count', 0)
            }
            
            await cache.set(cache_key, stats, expire=60)
        
        return stats
    
    @staticmethod
    async def end_contest(contest_id: int) -> bool:
        try:
            await db.update_contest_status(contest_id, 'ended')
            winners = await ContestService.select_winners(contest_id)
            
            await cache.delete(f"contest:{contest_id}")
            await cache.delete("active_contests")
            
            return len(winners) > 0
        except Exception as e:
            logger.error(f"Error ending contest {contest_id}: {e}")
            return False
    
    @staticmethod
    async def get_trending_contests(limit: int = 10) -> List[Dict[str, Any]]:
        cache_key = f"trending_contests:{limit}"
        contests = await cache.get(cache_key)
        
        if not contests:
            contests = await db.get_active_contests()
            contests = sorted(contests, key=lambda x: x.get('participant_count', 0), reverse=True)[:limit]
            await cache.set(cache_key, contests, expire=300)
        
        return contests
