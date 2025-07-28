from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.services.user_service import UserService
from app.services.broadcast_service import BroadcastService
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import SubscriptionService
from app.keyboards.inline import kb
from app.locales.translations import get_text
from app.core.config import settings

router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_button = State()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q" if lang == "uz" else "Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 *Reklama xabarini yuboring:*\n\n• Matn\n• Rasm + matn\n• Video + matn\n\nKeyingi bosqichda tugma qo'shishingiz mumkin." if lang == "uz" else "📢 *Отправьте рекламное сообщение:*\n\n• Текст\n• Фото + текст\n• Видео + текст\n\nНа следующем шаге можете добавить кнопку.",
        reply_markup=None,
        parse_mode="Markdown"
    )
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext, lang: str):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    await state.update_data(
        message_text=message.text or message.caption,
        photo_file_id=message.photo[-1].file_id if message.photo else None,
        video_file_id=message.video.file_id if message.video else None
    )
    
    await message.answer(
        "🔘 *Tugma qo'shasizmi?*\n\nFormat: Tugma matni | URL\nMasalan: Kanalga o'tish | https://t.me/channel\n\nYoki 'yo'q' deb yozing." if lang == "uz" else "🔘 *Добавить кнопку?*\n\nФормат: Текст кнопки | URL\nНапример: Перейти в канал | https://t.me/channel\n\nИли напишите 'нет'.",
        parse_mode="Markdown"
    )
    await state.set_state(BroadcastStates.waiting_for_button)

@router.message(BroadcastStates.waiting_for_button)
async def process_broadcast_button(message: Message, state: FSMContext, db: AsyncSession, lang: str):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    broadcast_data = await state.get_data()
    button_text = None
    button_url = None
    
    if message.text.lower() not in ['yo\'q', 'нет', 'no']:
        try:
            button_text, button_url = message.text.split(' | ')
        except ValueError:
            await message.answer("Noto'g'ri format!" if lang == "uz" else "Неверный формат!")
            return
    
    broadcast_service = BroadcastService(db)
    
    await message.answer("📤 Reklama yuborilmoqda..." if lang == "uz" else "📤 Отправка рекламы...")
    
    success_count = await broadcast_service.send_advanced_broadcast(
        admin_id=message.from_user.id,
        message_text=broadcast_data.get("message_text"),
        photo_file_id=broadcast_data.get("photo_file_id"),
        video_file_id=broadcast_data.get("video_file_id"),
        button_text=button_text,
        button_url=button_url,
        bot=message.bot
    )
    
    await message.answer(
        f"✅ *Reklama yuborildi!*\n\n📊 Muvaffaqiyatli: {success_count} foydalanuvchi" if lang == "uz" else f"✅ *Реклама отправлена!*\n\n📊 Успешно: {success_count} пользователей",
        reply_markup=kb.admin_panel(lang),
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q" if lang == "uz" else "Доступ запрещен", show_alert=True)
        return
    
    analytics_service = AnalyticsService(db)
    stats = await analytics_service.get_system_analytics()
    
    text = f"""📊 *Tizim statistikasi:*

👥 **Foydalanuvchilar:**
• Jami: {stats['total_users']}
• Faol: {stats['active_users']}
• Bugun yangi: {stats['new_today']}
• Premium: {stats['premium_users']}

🏆 **Konkurslar:**
• Jami: {stats['total_contests']}
• Faol: {stats['active_contests']}
• Tugagan: {stats['ended_contests']}

📈 **Faollik:**
• Bugungi xabarlar: {stats['messages_today']}
• Haftalik o'sish: {stats['weekly_growth']:.1f}%

💾 **Tizim:**
• Uptime: {stats['uptime']} soat""" if lang == "uz" else f"""📊 *Системная статистика:*

👥 **Пользователи:**
• Всего: {stats['total_users']}
• Активных: {stats['active_users']}
• Новых сегодня: {stats['new_today']}
• Premium: {stats['premium_users']}

🏆 **Конкурсы:**
• Всего: {stats['total_contests']}
• Активных: {stats['active_contests']}
• Завершенных: {stats['ended_contests']}

📈 **Активность:**
• Сообщений сегодня: {stats['messages_today']}
• Недельный рост: {stats['weekly_growth']:.1f}%

💾 **Система:**
• Uptime: {stats['uptime']} часов"""
    
    await callback.message.edit_text(text, reply_markup=kb.admin_panel(lang), parse_mode="Markdown")
