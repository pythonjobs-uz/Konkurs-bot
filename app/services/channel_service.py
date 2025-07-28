from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional, Dict

from app.core.database import Channel
from app.core.redis import cache

class ChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_channel(
        self,
        channel_id: int,
        title: str,
        username: Optional[str],
        owner_id: int,
        member_count: int = 0
    ) -> Channel:
        result = await self.db.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        existing_channel = result.scalar_one_or_none()
        
        if existing_channel:
            existing_channel.title = title
            existing_channel.username = username
            existing_channel.owner_id = owner_id
            existing_channel.member_count = member_count
            existing_channel.is_active = True
            existing_channel.updated_at = func.now()
            await self.db.commit()
            await self.db.refresh(existing_channel)
            
            cache_key = f"user_channels:{owner_id}"
            await cache.delete(cache_key)
            
            return existing_channel
        
        channel = Channel(
            channel_id=channel_id,
            title=title,
            username=username,
            owner_id=owner_id,
            member_count=member_count
        )
        
        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)
        
        cache_key = f"user_channels:{owner_id}"
        await cache.delete(cache_key)
        
        return channel
    
    async def get_user_channels(self, user_id: int) -> List[Dict]:
        cache_key = f"user_channels:{user_id}"
        cached_channels = await cache.get(cache_key)
        
        if cached_channels:
            return cached_channels
        
        result = await self.db.execute(
            select(Channel).where(
                and_(
                    Channel.owner_id == user_id,
                    Channel.is_active == True
                )
            ).order_by(desc(Channel.member_count))
        )
        channels = result.scalars().all()
        
        channel_list = [
            {
                "channel_id": channel.channel_id,
                "title": channel.title,
                "username": channel.username,
                "member_count": channel.member_count
            }
            for channel in channels
        ]
        
        await cache.set(cache_key, channel_list, 1800)
        return channel_list
    
    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        cache_key = f"channel:{channel_id}"
        cached_channel = await cache.get(cache_key)
        
        if cached_channel:
            return cached_channel
        
        result = await self.db.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            await cache.set(cache_key, channel, 3600)
        
        return channel
    
    async def update_member_count(self, channel_id: int, member_count: int):
        result = await self.db.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            channel.member_count = member_count
            channel.updated_at = func.now()
            await self.db.commit()
            
            await cache.delete(f"channel:{channel_id}")
            await cache.delete(f"user_channels:{channel.owner_id}")
    
    async def deactivate_channel(self, channel_id: int):
        result = await self.db.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            channel.is_active = False
            channel.updated_at = func.now()
            await self.db.commit()
            
            await cache.delete(f"channel:{channel_id}")
            await cache.delete(f"user_channels:{channel.owner_id}")
    
    async def get_top_channels(self, limit: int = 10) -> List[Channel]:
        result = await self.db.execute(
            select(Channel)
            .where(Channel.is_active == True)
            .order_by(desc(Channel.member_count))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_all_active_channels(self) -> List[Channel]:
        result = await self.db.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return list(result.scalars().all())
