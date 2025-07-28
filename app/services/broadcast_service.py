from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging
from typing import Optional
from datetime import datetime

from app.services.user_service import UserService
from app.core.database import BroadcastMessage

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
        target_users: Optional[list] = None,
        bot=None
    ) -> int:
        user_service = UserService(self.db)
        
        if target_users:
            users = []
            for user_id in target_users:
                user = await user_service.get_user(user_id)
                if user and user.is_active and not user.is_banned:
                    users.append(user)
        else:
            users = await user_service.get_all_active_users()
        
        broadcast_record = BroadcastMessage(
            admin_id=admin_id,
            message_text=message_text,
            image_file_id=photo_file_id,
            button_text=button_text,
            button_url=button_url,
            target_users=target_users,
            total_count=len(users),
            status="sending"
        )
        
        self.db.add(broadcast_record)
        await self.db.commit()
        await self.db.refresh(broadcast_record)
        
        if not bot:
            logger.error("Bot instance not provided")
            return 0
        
        success_count = 0
        failed_count = 0
        
        keyboard = None
        if button_text and button_url:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=button_text, url=button_url)
            ]])
        
        for user in users:
            try:
                if photo_file_id:
                    await bot.send_photo(
                        chat_id=user.id,
                        photo=photo_file_id,
                        caption=message_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                elif video_file_id:
                    await bot.send_video(
                        chat_id=user.id,
                        video=video_file_id,
                        caption=message_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_message(
                        chat_id=user.id,
                        text=message_text or "📢 Test message",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                
                success_count += 1
                await asyncio.sleep(0.05)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to user {user.id}: {e}")
                continue
        
        broadcast_record.sent_count = success_count
        broadcast_record.failed_count = failed_count
        broadcast_record.status = "completed"
        broadcast_record.sent_at = datetime.utcnow()
        broadcast_record.completed_at = datetime.utcnow()
        
        await self.db.commit()
        
        return success_count
    
    async def send_targeted_broadcast(
        self,
        admin_id: int,
        message_text: str,
        user_filter: dict,
        bot=None
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
            target_users=[user.id for user in users],
            bot=bot
        )
    
    async def _get_users_by_language(self, language: str) -> list:
        from app.core.database import User
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(User).where(
                User.language_code == language,
                User.is_active == True,
                User.is_banned == False
            )
        )
        return list(result.scalars().all())
