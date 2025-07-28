from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import ForceSubChannel
from app.core.redis import cache

class SubscriptionService:
    def __init__(self):
        pass
    
    async def check_subscription(self, user_id: int, channel_id: int, bot) -> bool:
        cache_key = f"subscription:{user_id}:{channel_id}"
        cached_result = await cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            is_subscribed = member.status in ['member', 'administrator', 'creator']
            
            await cache.set(cache_key, is_subscribed, 300)
            return is_subscribed
        except (TelegramBadRequest, Exception):
            return False
    
    async def check_multiple_subscriptions(self, user_id: int, channel_ids: List[int], bot) -> bool:
        for channel_id in channel_ids:
            if not await self.check_subscription(user_id, channel_id, bot):
                return False
        return True
    
    async def get_force_sub_channels(self, db: AsyncSession) -> List[ForceSubChannel]:
        cache_key = "force_sub_channels"
        cached_channels = await cache.get(cache_key)
        
        if cached_channels:
            return cached_channels
        
        result = await db.execute(
            select(ForceSubChannel)
            .where(ForceSubChannel.is_active == True)
            .order_by(ForceSubChannel.priority.desc())
        )
        channels = list(result.scalars().all())
        
        await cache.set(cache_key, channels, 1800)
        return channels
    
    async def add_force_sub_channel(self, db: AsyncSession, channel_id: int, title: str, username: str = None):
        existing = await db.execute(
            select(ForceSubChannel).where(ForceSubChannel.channel_id == channel_id)
        )
        
        if existing.scalar_one_or_none():
            return False
        
        channel = ForceSubChannel(
            channel_id=channel_id,
            title=title,
            username=username
        )
        
        db.add(channel)
        await db.commit()
        
        await cache.delete("force_sub_channels")
        return True
    
    async def remove_force_sub_channel(self, db: AsyncSession, channel_id: int):
        result = await db.execute(
            select(ForceSubChannel).where(ForceSubChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            channel.is_active = False
            await db.commit()
            await cache.delete("force_sub_channels")
            return True
        
        return False
