from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
import time

from app.core.redis import cache
from app.core.config import settings
from app.locales.translations import get_text

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self.rate_limit = settings.RATE_LIMIT_MESSAGES
        self.window = settings.RATE_LIMIT_WINDOW
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        
        if user and user.id not in settings.ADMIN_IDS:
            key = f"throttle:{user.id}"
            current_time = int(time.time())
            
            requests = await cache.get(key) or []
            requests = [req for req in requests if current_time - req < self.window]
            
            if len(requests) >= self.rate_limit:
                lang = data.get("lang", "uz")
                if hasattr(event, 'answer'):
                    await event.answer(get_text("rate_limit", lang), show_alert=True)
                return
            
            requests.append(current_time)
            await cache.set(key, requests, self.window)
        
        return await handler(event, data)
