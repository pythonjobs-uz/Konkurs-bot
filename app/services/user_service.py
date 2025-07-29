from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.core.database import db
from app.core.redis import cache
from config import settings
import secrets

class UserService:
    @staticmethod
    async def get_user_with_cache(user_id: int) -> Optional[Dict[str, Any]]:
        cache_key = f"user:{user_id}"
        user = await cache.get(cache_key)
        
        if not user:
            user = await db.get_user(user_id)
            if user:
                await cache.set(cache_key, user, expire=300)
        
        return user
    
    @staticmethod
    async def update_user_premium(user_id: int, premium_until: datetime) -> bool:
        try:
            await db.connection.execute("""
                UPDATE users SET is_premium = 1, premium_until = ? WHERE id = ?
            """, (premium_until.isoformat(), user_id))
            await db.connection.commit()
            
            await cache.delete(f"user:{user_id}")
            return True
        except Exception:
            return False
    
    @staticmethod
    async def check_premium_status(user_id: int) -> bool:
        user = await UserService.get_user_with_cache(user_id)
        if not user or not user.get('is_premium'):
            return False
        
        if user.get('premium_until'):
            premium_until = datetime.fromisoformat(user['premium_until'])
            if premium_until < datetime.now():
                await db.connection.execute("""
                    UPDATE users SET is_premium = 0, premium_until = NULL WHERE id = ?
                """, (user_id,))
                await db.connection.commit()
                await cache.delete(f"user:{user_id}")
                return False
        
        return True
    
    @staticmethod
    async def get_referral_info(user_id: int) -> Dict[str, Any]:
        user = await UserService.get_user_with_cache(user_id)
        if not user:
            return {}
        
        referral_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user['referral_code']}"
        
        cursor = await db.connection.execute("""
            SELECT COUNT(*) FROM users WHERE referred_by = ?
        """, (user_id,))
        referrals_count = (await cursor.fetchone())[0]
        
        bonus_amount = referrals_count * 5000
        
        return {
            "referral_code": user['referral_code'],
            "referral_link": referral_link,
            "referrals_count": referrals_count,
            "bonus_amount": bonus_amount
        }
    
    @staticmethod
    async def process_referral(user_id: int, referral_code: str) -> bool:
        try:
            cursor = await db.connection.execute("""
                SELECT id FROM users WHERE referral_code = ?
            """, (referral_code,))
            referrer = await cursor.fetchone()
            
            if referrer and referrer[0] != user_id:
                await db.connection.execute("""
                    UPDATE users SET referred_by = ?, total_referrals = total_referrals + 1 
                    WHERE id = ?
                """, (referrer[0], user_id))
                
                await db.connection.execute("""
                    UPDATE users SET total_referrals = total_referrals + 1 WHERE id = ?
                """, (referrer[0],))
                
                await db.connection.commit()
                
                await cache.delete(f"user:{user_id}")
                await cache.delete(f"user:{referrer[0]}")
                
                return True
        except Exception:
            pass
        
        return False
    
    @staticmethod
    async def get_user_analytics(user_id: int, days: int = 30) -> Dict[str, Any]:
        cache_key = f"user_analytics:{user_id}:{days}"
        analytics = await cache.get(cache_key)
        
        if not analytics:
            cursor = await db.connection.execute("""
                SELECT COUNT(*) FROM contests WHERE owner_id = ? 
                AND created_at >= datetime('now', '-{} days')
            """.format(days), (user_id,))
            contests_created = (await cursor.fetchone())[0]
            
            cursor = await db.connection.execute("""
                SELECT COUNT(*) FROM participants p
                JOIN contests c ON p.contest_id = c.id
                WHERE c.owner_id = ? AND p.joined_at >= datetime('now', '-{} days')
            """.format(days), (user_id,))
            total_participants = (await cursor.fetchone())[0]
            
            cursor = await db.connection.execute("""
                SELECT COUNT(*) FROM participants WHERE user_id = ? 
                AND joined_at >= datetime('now', '-{} days')
            """.format(days), (user_id,))
            participated_contests = (await cursor.fetchone())[0]
            
            cursor = await db.connection.execute("""
                SELECT COUNT(*) FROM winners WHERE user_id = ? 
                AND announced_at >= datetime('now', '-{} days')
            """.format(days), (user_id,))
            won_contests = (await cursor.fetchone())[0]
            
            analytics = {
                "contests_created": contests_created,
                "total_participants": total_participants,
                "participated_contests": participated_contests,
                "won_contests": won_contests,
                "success_rate": (won_contests / participated_contests * 100) if participated_contests > 0 else 0
            }
            
            await cache.set(cache_key, analytics, expire=3600)
        
        return analytics
