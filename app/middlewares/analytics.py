from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from typing import Callable, Dict, Any, Awaitable
from app.core.database import db

class AnalyticsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Update):
            user_id = None
            action = "unknown"
            
            if event.message:
                user_id = event.message.from_user.id
                action = f"message:{event.message.text[:20] if event.message.text else 'media'}"
            elif event.callback_query:
                user_id = event.callback_query.from_user.id
                action = f"callback:{event.callback_query.data}"
            
            if user_id:
                await db.log_analytics(
                    user_id=user_id,
                    action=action,
                    data=str(event.model_dump())[:500]
                )
        
        return await handler(event, data)
