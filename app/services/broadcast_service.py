from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.services.user_service import UserService
from app.core.database import BroadcastMessage, db

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
        target_users: Optional[List[int]] = None,
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
    
    @staticmethod
    async def send_broadcast(bot: Bot, message_data: Dict[str, Any], 
                           target_users: List[int] = None) -> Dict[str, int]:
        if target_users is None:
            users = await db.get_all_active_users()
            target_users = [user['id'] for user in users]
        
        success_count = 0
        failed_count = 0
        blocked_count = 0
        
        for user_id in target_users:
            try:
                if message_data.get('photo'):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=message_data['photo'],
                        caption=message_data.get('caption', ''),
                        parse_mode=message_data.get('parse_mode', 'HTML')
                    )
                elif message_data.get('video'):
                    await bot.send_video(
                        chat_id=user_id,
                        video=message_data['video'],
                        caption=message_data.get('caption', ''),
                        parse_mode=message_data.get('parse_mode', 'HTML')
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=message_data['text'],
                        parse_mode=message_data.get('parse_mode', 'HTML')
                    )
                
                success_count += 1
                await asyncio.sleep(0.05)
                
            except Exception as e:
                error_str = str(e).lower()
                if 'blocked' in error_str or 'deactivated' in error_str:
                    blocked_count += 1
                    await db.connection.execute("""
                        UPDATE users SET is_active = 0 WHERE id = ?
                    """, (user_id,))
                else:
                    failed_count += 1
                
                logger.warning(f"Failed to send message to {user_id}: {e}")
        
        await db.connection.commit()
        
        return {
            "success": success_count,
            "failed": failed_count,
            "blocked": blocked_count,
            "total": len(target_users)
        }
    
    @staticmethod
    async def send_targeted_broadcast(bot: Bot, message_data: Dict[str, Any], 
                                    filters: Dict[str, Any]) -> Dict[str, int]:
        query = "SELECT id FROM users WHERE is_active = 1 AND is_banned = 0"
        params = []
        
        if filters.get('is_premium') is not None:
            query += " AND is_premium = ?"
            params.append(filters['is_premium'])
        
        if filters.get('language_code'):
            query += " AND language_code = ?"
            params.append(filters['language_code'])
        
        if filters.get('created_after'):
            query += " AND created_at >= ?"
            params.append(filters['created_after'])
        
        cursor = await db.connection.execute(query, params)
        rows = await cursor.fetchall()
        target_users = [row[0] for row in rows]
        
        return await BroadcastService.send_broadcast(bot, message_data, target_users)
    
    @staticmethod
    async def send_contest_notification(bot: Bot, contest_id: int, notification_type: str):
        contest = await db.get_contest(contest_id)
        if not contest:
            return
        
        if notification_type == "started":
            participants = await db.get_contest_participants(contest_id)
            message_text = f"🎉 Konkurs boshlandi!\n\n🏆 {contest['title']}\n\n📝 {contest['description']}"
            
            for participant in participants:
                try:
                    await bot.send_message(
                        chat_id=participant['id'],
                        text=message_text,
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.warning(f"Failed to notify participant {participant['id']}: {e}")
        
        elif notification_type == "ended":
            winners = await db.get_contest_winners(contest_id)
            
            for winner in winners:
                try:
                    position_emoji = "🥇" if winner['position'] == 1 else "🥈" if winner['position'] == 2 else "🥉" if winner['position'] == 3 else "🏅"
                    message_text = f"🎉 Tabriklaymiz!\n\n{position_emoji} Siz {contest['title']} konkursida {winner['position']}-o'rin egasi bo'ldingiz!\n\nTez orada admin siz bilan bog'lanadi."
                    
                    await bot.send_message(
                        chat_id=winner['id'],
                        text=message_text,
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.warning(f"Failed to notify winner {winner['id']}: {e}")
    
    async def _get_users_by_language(self, language: str) -> List:
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
