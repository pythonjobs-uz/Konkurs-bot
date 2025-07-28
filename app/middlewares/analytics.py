from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from app.core.database import UserAnalytics

logger = logging.getLogger(__name__)

class AnalyticsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        result = await handler(event, data)
        
        try:
            await self.log_event(event, data)
        except Exception as e:
            logger.error(f"Analytics logging error: {e}")
        
        return result
    
    async def log_event(self, event: TelegramObject, data: Dict[str, Any]):
        if not isinstance(event, (Message, CallbackQuery)):
            return
        
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return
        
        db: AsyncSession = data.get("db")
        if not db:
            return
        
        action = self.get_action_name(event)
        event_data = self.extract_event_data(event)
        
        analytics = UserAnalytics(
            user_id=user_id,
            action=action,
            data=event_data
        )
        
        db.add(analytics)
        await db.commit()
    
    def get_action_name(self, event: TelegramObject) -> str:
        if isinstance(event, Message):
            if event.text and event.text.startswith('/'):
                return f"command:{event.text.split()[0]}"
            return "message"
        elif isinstance(event, CallbackQuery):
            return f"callback:{event.data}" if event.data else "callback"
        return "unknown"
    
    def extract_event_data(self, event: TelegramObject) -> Dict[str, Any]:
        data = {}
        
        if isinstance(event, Message):
            data.update({
                "message_id": event.message_id,
                "chat_type": event.chat.type if event.chat else None,
                "text_length": len(event.text) if event.text else 0
            })
        elif isinstance(event, CallbackQuery):
            data.update({
                "callback_data": event.data,
                "message_id": event.message.message_id if event.message else None
            })
        
        return data
