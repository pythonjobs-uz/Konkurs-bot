from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from typing import List, Optional, Dict

from app.core.database import Channel
from app.core.redis import redis_manager

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
            
            await redis_manager.delete(f"user_channels:{owner_id}")
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
        
        await redis_manager.delete(f"user_channels:{owner_id}")
        return channel
    
    async def get_user_channels(self, user_id: int) -> List[Dict]:
        cached_channels = await redis_manager.get(f"user_channels:{user_id}")
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
        
        await redis_manager.set(f"user_channels:{user_id}", channel_list, 1800)
        return channel_list
    
    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        cached_channel = await redis_manager.get(f"channel:{channel_id}")
        if cached_channel:
            return Channel(**cached_channel)
        
        result = await self.db.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            await redis_manager.set(f"channel:{channel_id}", {
                "id": channel.id,
                "channel_id": channel.channel_id,
                "title": channel.title,
                "username": channel.username,
                "owner_id": channel.owner_id,
                "member_count": channel.member_count,
                "is_active": channel.is_active
            }, 3600)
        
        return channel
