from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.core.database import User, Contest, Participant, UserAnalytics, ContestAnalytics
from app.core.redis import cache

class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def track_user_action(self, user_id: int, action: str, data: Dict[str, Any] = None):
        analytics = UserAnalytics(
            user_id=user_id,
            action=action,
            data=data or {}
        )
        
        self.db.add(analytics)
        await self.db.commit()
        
        await cache.delete(f"user_analytics:{user_id}")
    
    async def track_contest_metric(self, contest_id: int, metric_name: str, metric_value: float):
        analytics = ContestAnalytics(
            contest_id=contest_id,
            metric_name=metric_name,
            metric_value=metric_value
        )
        
        self.db.add(analytics)
        await self.db.commit()
        
        await cache.delete(f"contest_analytics:{contest_id}")
    
    async def get_user_analytics(self, user_id: int) -> Dict[str, Any]:
        cache_key = f"user_analytics:{user_id}"
        cached_analytics = await cache.get(cache_key)
        
        if cached_analytics:
            return cached_analytics
        
        try:
            total_contests = await self.db.execute(
                select(func.count(Contest.id)).where(Contest.owner_id == user_id)
            )
            
            active_contests = await self.db.execute(
                select(func.count(Contest.id)).where(
                    and_(Contest.owner_id == user_id, Contest.status == "active")
                )
            )
            
            completed_contests = await self.db.execute(
                select(func.count(Contest.id)).where(
                    and_(Contest.owner_id == user_id, Contest.status == "ended")
                )
            )
            
            cancelled_contests = await self.db.execute(
                select(func.count(Contest.id)).where(
                    and_(Contest.owner_id == user_id, Contest.status == "cancelled")
                )
            )
            
            total_participants = await self.db.execute(
                select(func.count(Participant.id))
                .join(Contest)
                .where(Contest.owner_id == user_id)
            )
            
            total_views = await self.db.execute(
                select(func.sum(Contest.view_count)).where(Contest.owner_id == user_id)
            )
            
            this_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month = (this_month - timedelta(days=1)).replace(day=1)
            
            this_month_contests = await self.db.execute(
                select(func.count(Contest.id)).where(
                    and_(
                        Contest.owner_id == user_id,
                        Contest.created_at >= this_month
                    )
                )
            )
            
            last_month_contests = await self.db.execute(
                select(func.count(Contest.id)).where(
                    and_(
                        Contest.owner_id == user_id,
                        Contest.created_at >= last_month,
                        Contest.created_at < this_month
                    )
                )
            )
            
            avg_participants_result = await self.db.execute(
                select(func.avg(Contest.participant_count)).where(
                    and_(Contest.owner_id == user_id, Contest.participant_count > 0)
                )
            )
            
            max_participants_result = await self.db.execute(
                select(func.max(Contest.participant_count)).where(Contest.owner_id == user_id)
            )
            
            min_participants_result = await self.db.execute(
                select(func.min(Contest.participant_count)).where(
                    and_(Contest.owner_id == user_id, Contest.participant_count > 0)
                )
            )
            
            analytics = {
                "total_contests": total_contests.scalar() or 0,
                "active_contests": active_contests.scalar() or 0,
                "completed_contests": completed_contests.scalar() or 0,
                "cancelled_contests": cancelled_contests.scalar() or 0,
                "total_participants": total_participants.scalar() or 0,
                "avg_participants": float(avg_participants_result.scalar() or 0),
                "max_participants": max_participants_result.scalar() or 0,
                "min_participants": min_participants_result.scalar() or 0,
                "total_views": total_views.scalar() or 0,
                "this_month_contests": this_month_contests.scalar() or 0,
                "last_month_contests": last_month_contests.scalar() or 0,
            }
            
            if analytics["last_month_contests"] > 0:
                analytics["growth_rate"] = ((analytics["this_month_contests"] - analytics["last_month_contests"]) / analytics["last_month_contests"]) * 100
            else:
                analytics["growth_rate"] = 0
            
            if analytics["total_views"] > 0 and analytics["total_participants"] > 0:
                analytics["ctr"] = (analytics["total_participants"] / analytics["total_views"]) * 100
            else:
                analytics["ctr"] = 0
            
            if analytics["total_contests"] > 0:
                analytics["participation_rate"] = (analytics["total_participants"] / analytics["total_contests"])
            else:
                analytics["participation_rate"] = 0
            
            await cache.set(cache_key, analytics, 1800)
            return analytics
        
        except Exception as e:
            return {
                "total_contests": 0,
                "active_contests": 0,
                "completed_contests": 0,
                "cancelled_contests": 0,
                "total_participants": 0,
                "avg_participants": 0,
                "max_participants": 0,
                "min_participants": 0,
                "total_views": 0,
                "this_month_contests": 0,
                "last_month_contests": 0,
                "growth_rate": 0,
                "ctr": 0,
                "participation_rate": 0
            }
    
    async def get_contest_analytics(self, contest_id: int) -> Dict[str, Any]:
        cache_key = f"contest_analytics:{contest_id}"
        cached_analytics = await cache.get(cache_key)
        
        if cached_analytics:
            return cached_analytics
        
        try:
            result = await self.db.execute(
                select(ContestAnalytics)
                .where(ContestAnalytics.contest_id == contest_id)
                .order_by(desc(ContestAnalytics.timestamp))
            )
            
            metrics = result.scalars().all()
            analytics = {}
            
            for metric in metrics:
                if metric.metric_name not in analytics:
                    analytics[metric.metric_name] = []
                analytics[metric.metric_name].append({
                    "value": metric.metric_value,
                    "timestamp": metric.timestamp
                })
            
            await cache.set(cache_key, analytics, 900)
            return analytics
        
        except Exception:
            return {}
    
    async def get_system_analytics(self) -> Dict[str, Any]:
        cache_key = "system_analytics"
        cached_analytics = await cache.get(cache_key)
        
        if cached_analytics:
            return cached_analytics
        
        try:
            total_users = await self.db.execute(select(func.count(User.id)))
            active_users = await self.db.execute(
                select(func.count(User.id)).where(
                    and_(User.is_active == True, User.is_banned == False)
                )
            )
            premium_users = await self.db.execute(
                select(func.count(User.id)).where(
                    and_(User.is_active == True, User.is_premium == True, User.is_banned == False)
                )
            )
            
            today = datetime.now().date()
            new_today = await self.db.execute(
                select(func.count(User.id)).where(
                    func.date(User.created_at) == today
                )
            )
            
            total_contests = await self.db.execute(select(func.count(Contest.id)))
            active_contests = await self.db.execute(
                select(func.count(Contest.id)).where(Contest.status == "active")
            )
            ended_contests = await self.db.execute(
                select(func.count(Contest.id)).where(Contest.status == "ended")
            )
            
            messages_today = await self.db.execute(
                select(func.count(UserAnalytics.id)).where(
                    func.date(UserAnalytics.timestamp) == today
                )
            )
            
            week_ago = datetime.now() - timedelta(days=7)
            users_week_ago = await self.db.execute(
                select(func.count(User.id)).where(User.created_at <= week_ago)
            )
            
            weekly_growth = 0
            users_week_ago_count = users_week_ago.scalar() or 0
            if users_week_ago_count > 0:
                weekly_growth = ((total_users.scalar() - users_week_ago_count) / users_week_ago_count) * 100
            
            analytics = {
                "total_users": total_users.scalar() or 0,
                "active_users": active_users.scalar() or 0,
                "premium_users": premium_users.scalar() or 0,
                "new_today": new_today.scalar() or 0,
                "total_contests": total_contests.scalar() or 0,
                "active_contests": active_contests.scalar() or 0,
                "ended_contests": ended_contests.scalar() or 0,
                "messages_today": messages_today.scalar() or 0,
                "weekly_growth": weekly_growth,
                "top_channel": "N/A",
                "db_size": 0,
                "redis_memory": 0,
                "uptime": 24
            }
            
            await cache.set(cache_key, analytics, 600)
            return analytics
        
        except Exception:
            return {
                "total_users": 0,
                "active_users": 0,
                "premium_users": 0,
                "new_today": 0,
                "total_contests": 0,
                "active_contests": 0,
                "ended_contests": 0,
                "messages_today": 0,
                "weekly_growth": 0,
                "top_channel": "N/A",
                "db_size": 0,
                "redis_memory": 0,
                "uptime": 0
            }
    
    async def get_popular_contests(self, limit: int = 10) -> List[Contest]:
        try:
            result = await self.db.execute(
                select(Contest)
                .where(Contest.status == "active")
                .order_by(desc(Contest.view_count))
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception:
            return []
    
    async def get_engagement_metrics(self, contest_id: int) -> Dict[str, float]:
        try:
            contest = await self.db.execute(
                select(Contest).where(Contest.id == contest_id)
            )
            contest_obj = contest.scalar_one_or_none()
            
            if not contest_obj:
                return {}
            
            participants_count = await self.db.execute(
                select(func.count(Participant.id)).where(Participant.contest_id == contest_id)
            )
            
            engagement_rate = 0
            if contest_obj.view_count > 0:
                engagement_rate = (participants_count.scalar() / contest_obj.view_count) * 100
            
            return {
                "engagement_rate": engagement_rate,
                "views": contest_obj.view_count,
                "participants": participants_count.scalar() or 0
            }
        
        except Exception:
            return {
                "engagement_rate": 0,
                "views": 0,
                "participants": 0
            }
