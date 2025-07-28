from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging
from typing import Optional

from app.services.user_service import UserService
from app.core.database import BroadcastMessage
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

class BroadcastService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def send_advanced_broadcast(
        self,
        admin_id: int,
        message_text: Optional[str] = None,
        photo_file_id: Optional[str] = None,
        video_file_id: Optional[str] = None,
        button_text: Optional[str] = None,
        button_url: Optional[str] = None,
        target_users: Optional[list] = None
    ) -> int:
        user_service = UserService(self.db)
        
        if target_users:
            users = []
            for user_id in target_users:
                user = await user_service.get_user(user_id)
                if user:
                    users.append(user)
        else:
            users = await user_service.get_all_active_users()
        
        broadcast_record = BroadcastMessage(
            admin_id=admin_id,
            message_text=message_text,
            image_file_id=photo_file_id,
            button_text=button_text,
            button_url=button_url,
            target_users=target_users
        )
        
        self.db.add(broadcast_record)
        await self.db.commit()
        await self.db.refresh(broadcast_record)
        
        success_count = 0
        failed_count = 0
        
        keyboard = None
        if button_text and button_url:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=button_text, url=button_url)
            ]])
        
        from main import bot
        
        for user in users:
            try:
                if photo_file_id:
                    await bot.send_photo(
                        chat_id=user.id,
                        photo=photo_file_id,
                        caption=message_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                elif video_file_id:
                    await bot.send_video(
                        chat_id=user.id,
                        video=video_file_id,
                        caption=message_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                else:
                    await bot.send_message(
                        chat_id=user.id,
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                
                success_count += 1
                await asyncio.sleep(0.03)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to user {user.id}: {e}")
                continue
        
        broadcast_record.sent_count = success_count
        broadcast_record.failed_count = failed_count
        broadcast_record.status = "completed"
        broadcast_record.sent_at = datetime.utcnow()
        
        await self.db.commit()
        
        metrics.record_message("broadcast")
        
        return success_count
    
    async def send_targeted_broadcast(
        self,
        admin_id: int,
        message_text: str,
        user_filter: dict
    ) -> int:
        user_service = UserService(self.db)
        
        if user_filter.get("premium_only"):
            users = await user_service.get_premium_users()
        elif user_filter.get("language"):
            users = await self._get_users_by_language(user_filter["language"])
        else:
            users = await user_service.get_all_active_users()
        
        return await self.send_advanced_broadcast(
            admin_id=admin_id,
            message_text=message_text,
            target_users=[user.id for user in users]
        )
    
    async def _get_users_by_language(self, language: str) -> list:
        from app.core.database import User
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(User).where(
                User.language_code == language,
                User.is_active == True
            )
        )
        return result.scalars().all()
