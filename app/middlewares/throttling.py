from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import time
import logging

from app.core.redis import redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self.rate_limit = settings.RATE_LIMIT_MESSAGES
        self.time_window = settings.RATE_LIMIT_WINDOW
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
            
            if user_id and not await self.check_rate_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return
        
        return await handler(event, data)
    
    async def check_rate_limit(self, user_id: int) -> bool:
        if not redis_manager.redis:
            return True
        
        key = f"rate_limit:{user_id}"
        current_time = int(time.time())
        
        try:
            pipe = redis_manager.redis.pipeline()
            pipe.zremrangebyscore(key, 0, current_time - self.time_window)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, self.time_window)
            
            results = await pipe.execute()
            request_count = results[1]
            
            return request_count < self.rate_limit
        
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return True
