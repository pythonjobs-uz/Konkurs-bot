from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from app.core.redis import cache
import time

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: int = 30, window: int = 60):
        self.rate_limit = rate_limit
        self.window = window
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if user_id:
            key = f"throttle:{user_id}"
            current_time = int(time.time())
            
            requests = await cache.get(key) or []
            requests = [req for req in requests if current_time - req < self.window]
            
            if len(requests) >= self.rate_limit:
                if isinstance(event, Message):
                    await event.answer("⚠️ Juda ko'p so'rov! Biroz kuting.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Juda ko'p so'rov! Biroz kuting.", show_alert=True)
                return
            
            requests.append(current_time)
            await cache.set(key, requests, expire=self.window)
        
        return await handler(event, data)
