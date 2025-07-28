import redis.asyncio as redis
from typing import Optional, Any
import json
import pickle
from datetime import timedelta

from app.core.config import settings

redis_client: Optional[redis.Redis] = None

async def init_redis():
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.ping()

async def get_redis() -> redis.Redis:
    return redis_client

class CacheManager:
    def __init__(self):
        self.redis = redis_client
    
    async def set(self, key: str, value: Any, expire: int = 3600):
        serialized = pickle.dumps(value)
        await self.redis.set(key, serialized, ex=expire)
    
    async def get(self, key: str) -> Any:
        data = await self.redis.get(key)
        if data:
            return pickle.loads(data)
        return None
    
    async def delete(self, key: str):
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key)
    
    async def increment(self, key: str, amount: int = 1) -> int:
        return await self.redis.incr(key, amount)
    
    async def set_with_ttl(self, key: str, value: Any, ttl: timedelta):
        serialized = pickle.dumps(value)
        await self.redis.setex(key, ttl, serialized)

cache = CacheManager()
