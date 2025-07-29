from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.core.database import User, Contest, Participant, UserAnalytics, ContestAnalytics
from app.core.redis import cache
import json

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
    
    @staticmethod
    async def get_system_analytics(days: int = 7) -> Dict[str, Any]:
        cache_key = f"system_analytics:{days}"
        analytics = await cache.get(cache_key)
        
        if not analytics:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # User growth
            cursor = await db.connection.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM users 
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY DATE(created_at) 
                ORDER BY date
            """, (start_date.isoformat(), end_date.isoformat()))
            user_growth = await cursor.fetchall()
            
            # Contest creation stats
            cursor = await db.connection.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM contests 
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY DATE(created_at) 
                ORDER BY date
            """, (start_date.isoformat(), end_date.isoformat()))
            contest_creation = await cursor.fetchall()
            
            # Participation stats
            cursor = await db.connection.execute("""
                SELECT DATE(joined_at) as date, COUNT(*) as count 
                FROM participants 
                WHERE joined_at >= ? AND joined_at <= ?
                GROUP BY DATE(joined_at) 
                ORDER BY date
            """, (start_date.isoformat(), end_date.isoformat()))
            participation_stats = await cursor.fetchall()
            
            # Top channels by contests
            cursor = await db.connection.execute("""
                SELECT c.title, COUNT(co.id) as contest_count, SUM(co.participant_count) as total_participants
                FROM channels c
                LEFT JOIN contests co ON c.channel_id = co.channel_id
                WHERE co.created_at >= ? AND co.created_at <= ?
                GROUP BY c.id
                ORDER BY contest_count DESC
                LIMIT 10
            """, (start_date.isoformat(), end_date.isoformat()))
            top_channels = await cursor.fetchall()
            
            # Most active users
            cursor = await db.connection.execute("""
                SELECT u.first_name, u.username, COUNT(c.id) as contest_count
                FROM users u
                LEFT JOIN contests c ON u.id = c.owner_id
                WHERE c.created_at >= ? AND c.created_at <= ?
                GROUP BY u.id
                ORDER BY contest_count DESC
                LIMIT 10
            """, (start_date.isoformat(), end_date.isoformat()))
            active_users = await cursor.fetchall()
            
            analytics = {
                "user_growth": [{"date": row[0], "count": row[1]} for row in user_growth],
                "contest_creation": [{"date": row[0], "count": row[1]} for row in contest_creation],
                "participation_stats": [{"date": row[0], "count": row[1]} for row in participation_stats],
                "top_channels": [{"title": row[0], "contests": row[1], "participants": row[2]} for row in top_channels],
                "active_users": [{"name": row[0], "username": row[1], "contests": row[2]} for row in active_users]
            }
            
            await cache.set(cache_key, analytics, expire=3600)
        
        return analytics
    
    @staticmethod
    async def get_contest_analytics(contest_id: int) -> Dict[str, Any]:
        cache_key = f"contest_analytics:{contest_id}"
        analytics = await cache.get(cache_key)
        
        if not analytics:
            contest = await db.get_contest(contest_id)
            if not contest:
                return {}
            
            # Participation timeline
            cursor = await db.connection.execute("""
                SELECT DATE(joined_at) as date, COUNT(*) as count 
                FROM participants 
                WHERE contest_id = ?
                GROUP BY DATE(joined_at) 
                ORDER BY date
            """, (contest_id,))
            participation_timeline = await cursor.fetchall()
            
            # Hourly participation
            cursor = await db.connection.execute("""
                SELECT strftime('%H', joined_at) as hour, COUNT(*) as count 
                FROM participants 
                WHERE contest_id = ?
                GROUP BY strftime('%H', joined_at) 
                ORDER BY hour
            """, (contest_id,))
            hourly_participation = await cursor.fetchall()
            
            # Referral sources
            cursor = await db.connection.execute("""
                SELECT referral_source, COUNT(*) as count 
                FROM participants 
                WHERE contest_id = ? AND referral_source IS NOT NULL
                GROUP BY referral_source 
                ORDER BY count DESC
            """, (contest_id,))
            referral_sources = await cursor.fetchall()
            
            analytics = {
                "contest": contest,
                "participation_timeline": [{"date": row[0], "count": row[1]} for row in participation_timeline],
                "hourly_participation": [{"hour": row[0], "count": row[1]} for row in hourly_participation],
                "referral_sources": [{"source": row[0], "count": row[1]} for row in referral_sources]
            }
            
            await cache.set(cache_key, analytics, expire=1800)
        
        return analytics
    
    @staticmethod
    async def get_user_engagement_metrics() -> Dict[str, Any]:
        cache_key = "user_engagement_metrics"
        metrics = await cache.get(cache_key)
        
        if not metrics:
            # Daily active users
            cursor = await db.connection.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM analytics 
                WHERE created_at >= datetime('now', '-1 day')
            """)
            daily_active = (await cursor.fetchone())[0]
            
            # Weekly active users
            cursor = await db.connection.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM analytics 
                WHERE created_at >= datetime('now', '-7 days')
            """)
            weekly_active = (await cursor.fetchone())[0]
            
            # Monthly active users
            cursor = await db.connection.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM analytics 
                WHERE created_at >= datetime('now', '-30 days')
            """)
            monthly_active = (await cursor.fetchone())[0]
            
            # Average session duration (approximated)
            cursor = await db.connection.execute("""
                SELECT AVG(session_count) as avg_actions_per_session
                FROM (
                    SELECT user_id, COUNT(*) as session_count
                    FROM analytics 
                    WHERE created_at >= datetime('now', '-7 days')
                    GROUP BY user_id, DATE(created_at)
                ) sessions
            """)
            avg_session_actions = (await cursor.fetchone())[0] or 0
            
            metrics = {
                "daily_active_users": daily_active,
                "weekly_active_users": weekly_active,
                "monthly_active_users": monthly_active,
                "avg_session_actions": round(avg_session_actions, 2)
            }
            
            await cache.set(cache_key, metrics, expire=1800)
        
        return metrics
    
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
