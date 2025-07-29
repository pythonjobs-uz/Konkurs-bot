from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.core.database import db
from app.keyboards.inline import admin_panel_keyboard, back_to_menu_keyboard
from app.locales.translations import get_text
from app.services.broadcast_service import BroadcastService
from app.services.analytics_service import AnalyticsService
from config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)
router = Router()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    stats = await db.get_statistics()
    
    text = "👨‍💻 *Admin Panel*\n\n"
    text += f"📊 Tizim statistikasi:\n"
    text += f"• Jami foydalanuvchilar: {stats['total_users']:,}\n"
    text += f"• Faol foydalanuvchilar: {stats['active_users']:,}\n"
    text += f"• Premium foydalanuvchilar: {stats['premium_users']:,}\n"
    text += f"• Jami konkurslar: {stats['total_contests']:,}\n"
    text += f"• Faol konkurslar: {stats['active_contests']:,}\n"
    text += f"• Jami qatnashchilar: {stats['total_participants']:,}\n"
    text += f"• Jami g'oliblar: {stats['total_winners']:,}\n"
    
    await message.answer(
        text,
        reply_markup=admin_panel_keyboard(lang),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await callback.message.edit_text(
        "📢 *Reklama xabarini yuboring:*\n\nMatn, rasm yoki video yuborishingiz mumkin." if lang == "uz" else "📢 *Отправьте рекламное сообщение:*\n\nВы можете отправить текст, изображение или видео.",
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(BroadcastState.waiting_for_message)

@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await message.answer("📤 Reklama yuborilmoqda..." if lang == "uz" else "📤 Отправка рекламы...")
    
    message_data = {}
    
    if message.photo:
        message_data = {
            'photo': message.photo[-1].file_id,
            'caption': message.caption or '',
            'parse_mode': 'HTML'
        }
    elif message.video:
        message_data = {
            'video': message.video.file_id,
            'caption': message.caption or '',
            'parse_mode': 'HTML'
        }
    else:
        message_data = {
            'text': message.text,
            'parse_mode': 'HTML'
        }
    
    result = await BroadcastService.send_broadcast(message.bot, message_data)
    
    await message.answer(
        f"✅ *Reklama yuborildi!*\n\n📊 Natijalar:\n• Muvaffaqiyatli: {result['success']:,}\n• Xatolik: {result['failed']:,}\n• Bloklangan: {result['blocked']:,}\n• Jami: {result['total']:,}" if lang == "uz" else f"✅ *Реклама отправлена!*\n\n📊 Результаты:\n• Успешно: {result['success']:,}\n• Ошибок: {result['failed']:,}\n• Заблокировано: {result['blocked']:,}\n• Всего: {result['total']:,}",
        reply_markup=admin_panel_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    stats = await db.get_statistics()
    engagement = await AnalyticsService.get_user_engagement_metrics()
    
    text = "📊 *Tizim statistikasi:*\n\n" if lang == "uz" else "📊 *Системная статистика:*\n\n"
    text += f"👥 **Foydalanuvchilar:**\n"
    text += f"• Jami: {stats['total_users']:,}\n"
    text += f"• Faol: {stats['active_users']:,}\n"
    text += f"• Premium: {stats['premium_users']:,}\n\n"
    text += f"🏆 **Konkurslar:**\n"
    text += f"• Jami: {stats['total_contests']:,}\n"
    text += f"• Faol: {stats['active_contests']:,}\n\n"
    text += f"👥 **Qatnashish:**\n"
    text += f"• Jami qatnashchilar: {stats['total_participants']:,}\n"
    text += f"• Jami g'oliblar: {stats['total_winners']:,}\n\n"
    text += f"📈 **Faollik:**\n"
    text += f"• Kunlik faol: {engagement['daily_active_users']:,}\n"
    text += f"• Haftalik faol: {engagement['weekly_active_users']:,}\n"
    text += f"• Oylik faol: {engagement['monthly_active_users']:,}\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=admin_panel_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_analytics")
async def admin_analytics_callback(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    analytics = await AnalyticsService.get_system_analytics(days=7)
    
    text = "📈 *7 kunlik analitika:*\n\n" if lang == "uz" else "📈 *Аналитика за 7 дней:*\n\n"
    
    if analytics['user_growth']:
        text += "👥 **Foydalanuvchilar o'sishi:**\n"
        for day in analytics['user_growth'][-3:]:
            text += f"• {day['date']}: +{day['count']}\n"
        text += "\n"
    
    if analytics['contest_creation']:
        text += "🏆 **Konkurslar yaratilishi:**\n"
        for day in analytics['contest_creation'][-3:]:
            text += f"• {day['date']}: {day['count']}\n"
        text += "\n"
    
    if analytics['top_channels']:
        text += "🔝 **Top kanallar:**\n"
        for channel in analytics['top_channels'][:3]:
            text += f"• {channel['title']}: {channel['contests']} konkurs\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=admin_panel_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    cursor = await db.connection.execute("""
        SELECT COUNT(*) as count, language_code 
        FROM users 
        GROUP BY language_code
    """)
    lang_stats = await cursor.fetchall()
    
    cursor = await db.connection.execute("""
        SELECT first_name, username, created_at 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent_users = await cursor.fetchall()
    
    text = "👥 *Foydalanuvchilar boshqaruvi:*\n\n" if lang == "uz" else "👥 *Управление пользователями:*\n\n"
    
    text += "🌐 **Tillar bo'yicha:**\n"
    for stat in lang_stats:
        lang_name = "O'zbekcha" if stat[1] == "uz" else "Русский" if stat[1] == "ru" else stat[1]
        text += f"• {lang_name}: {stat[0]:,}\n"
    
    text += "\n🆕 **So'nggi foydalanuvchilar:**\n"
    for user_data in recent_users:
        name = user_data[0] or "Noma'lum"
        username = f"@{user_data[1]}" if user_data[1] else ""
        text += f"• {name} {username}\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=admin_panel_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_contests")
async def admin_contests_callback(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    cursor = await db.connection.execute("""
        SELECT status, COUNT(*) as count 
        FROM contests 
        GROUP BY status
    """)
    status_stats = await cursor.fetchall()
    
    cursor = await db.connection.execute("""
        SELECT c.title, c.participant_count, u.first_name 
        FROM contests c
        JOIN users u ON c.owner_id = u.id
        ORDER BY c.participant_count DESC 
        LIMIT 5
    """)
    top_contests = await cursor.fetchall()
    
    text = "🏆 *Konkurslar boshqaruvi:*\n\n" if lang == "uz" else "🏆 *Управление конкурсами:*\n\n"
    
    text += "📊 **Status bo'yicha:**\n"
    status_names = {
        'pending': 'Kutilmoqda',
        'active': 'Faol',
        'ended': 'Tugagan',
        'cancelled': 'Bekor qilingan'
    }
    for stat in status_stats:
        status_name = status_names.get(stat[0], stat[0])
        text += f"• {status_name}: {stat[1]:,}\n"
    
    text += "\n🔝 **Top konkurslar:**\n"
    for contest in top_contests:
        text += f"• {contest[0][:30]}... ({contest[1]} qatnashuvchi)\n"
        text += f"  👤 {contest[2]}\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=admin_panel_keyboard(lang), 
        parse_mode="Markdown"
    )
