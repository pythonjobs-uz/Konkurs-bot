import redis.asyncio as redis
from config import settings
import json
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self.redis = None
    
    async def init_redis(self):
        try:
            self.redis = redis.from_url(settings.REDIS_URL)
            await self.redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.redis = None
    
    async def close(self):
        if self.redis:
            await self.redis.close()
    
    async def get(self, key: str):
        if not self.redis:
            return None
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value, expire: int = 3600):
        if not self.redis:
            return False
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str):
        if not self.redis:
            return False
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1):
        if not self.redis:
            return 0
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return 0

cache = RedisCache()
