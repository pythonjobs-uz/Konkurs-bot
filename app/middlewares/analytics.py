from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, Message, CallbackQuery
import time

from app.core.metrics import metrics

class AnalyticsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        start_time = time.time()
        
        if isinstance(event, Message):
            metrics.record_message("message")
        elif isinstance(event, CallbackQuery):
            metrics.record_message("callback")
        
        try:
            result = await handler(event, data)
            return result
        finally:
            duration = time.time() - start_time
            metrics.record_response_time(duration)
