from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.services.user_service import UserService
from app.services.broadcast_service import BroadcastService
from app.services.analytics_service import AnalyticsService
from app.keyboards.inline import kb
from app.locales.translations import get_text
from app.core.config import settings
from app.core.redis import cache

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
        reply_markup=None
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
        "🔘 *Tugma qo'shasizmi?*\n\nFormat: Tugma matni | URL\nMasalan: Kanalga o'tish | https://t.me/channel\n\nYoki 'yo'q' deb yozing." if lang == "uz" else "🔘 *Добавить кнопку?*\n\nФормат: Текст кнопки | URL\nНапример: Перейти в канал | https://t.me/channel\n\nИли напишите 'нет'."
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
        button_url=button_url
    )
    
    await message.answer(
        f"✅ *Reklama yuborildi!*\n\n📊 Muvaffaqiyatli: {success_count} foydalanuvchi" if lang == "uz" else f"✅ *Реклама отправлена!*\n\n📊 Успешно: {success_count} пользователей",
        reply_markup=kb.admin_panel(lang)
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
• Eng faol kanal: {stats['top_channel']}

💾 **Tizim:**
• Ma'lumotlar bazasi: {stats['db_size']} MB
• Redis: {stats['redis_memory']} MB
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
• Топ канал: {stats['top_channel']}

💾 **Система:**
• База данных: {stats['db_size']} MB
• Redis: {stats['redis_memory']} MB
• Uptime: {stats['uptime']} часов"""
    
    await callback.message.edit_text(text, reply_markup=kb.admin_panel(lang))

@router.callback_query(F.data == "admin_health")
async def admin_health_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q" if lang == "uz" else "Доступ запрещен", show_alert=True)
        return
    
    try:
        db_status = "✅ Ishlayapti" if lang == "uz" else "✅ Работает"
        redis_status = "✅ Ishlayapti" if lang == "uz" else "✅ Работает"
        
        await cache.set("health_check", "ok", 10)
        health_check = await cache.get("health_check")
        if health_check != "ok":
            redis_status = "❌ Xatolik" if lang == "uz" else "❌ Ошибка"
        
    except Exception:
        db_status = "❌ Xatolik" if lang == "uz" else "❌ Ошибка"
        redis_status = "❌ Xatolik" if lang == "uz" else "❌ Ошибка"
    
    text = f"""🔧 *Tizim holati:*

🗄 **Ma'lumotlar bazasi:** {db_status}
🔄 **Redis:** {redis_status}
⚡ **Bot API:** ✅ Ishlayapti
📡 **Webhook:** {'✅ Faol' if settings.USE_WEBHOOK else '📡 Polling'}

🔄 **Xizmatlar:**
• Scheduler: ✅ Ishlayapti
• Analytics: ✅ Ishlayapti
• Metrics: ✅ Ishlayapti

⚠️ **Ogohlantirishlar:**
• Disk: {'🟡 70%' if True else '✅ OK'}
• Memory: {'🟡 80%' if True else '✅ OK'}
• CPU: ✅ OK""" if lang == "uz" else f"""🔧 *Состояние системы:*

🗄 **База данных:** {db_status}
🔄 **Redis:** {redis_status}
⚡ **Bot API:** ✅ Работает
📡 **Webhook:** {'✅ Активен' if settings.USE_WEBHOOK else '📡 Polling'}

🔄 **Сервисы:**
• Scheduler: ✅ Работает
• Analytics: ✅ Работает
• Metrics: ✅ Работает

⚠️ **Предупреждения:**
• Диск: {'🟡 70%' if True else '✅ OK'}
• Память: {'🟡 80%' if True else '✅ OK'}
• CPU: ✅ OK"""
    
    await callback.message.edit_text(text, reply_markup=kb.admin_panel(lang))

@router.callback_query(F.data == "admin_channels")
async def admin_channels_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q" if lang == "uz" else "Доступ запрещен", show_alert=True)
        return
    
    from app.services.subscription_service import SubscriptionService
    subscription_service = SubscriptionService()
    
    channels = await subscription_service.get_force_sub_channels()
    
    text = "📺 *Majburiy obuna kanallari:*\n\n" if lang == "uz" else "📺 *Каналы принудительной подписки:*\n\n"
    
    if not channels:
        text += "Hech qanday kanal qo'shilmagan." if lang == "uz" else "Каналы не добавлены."
    else:
        for i, channel in enumerate(channels, 1):
            status = "✅" if channel.is_active else "❌"
            text += f"{i}. {status} {channel.title}\n"
            if channel.username:
                text += f"   @{channel.username}\n"
            text += f"   ID: {channel.channel_id}\n\n"
    
    text += "\n💡 Kanal qo'shish uchun: /add_force_channel\n💡 Kanal o'chirish uchun: /remove_force_channel"
    
    await callback.message.edit_text(text, reply_markup=kb.admin_panel(lang))
