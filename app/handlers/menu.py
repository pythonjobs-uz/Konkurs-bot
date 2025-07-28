from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.contest_service import ContestService
from app.services.analytics_service import AnalyticsService
from app.services.channel_service import ChannelService
from app.keyboards.inline import kb
from app.locales.translations import get_text
from app.core.config import settings

router = Router()

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    user_service = UserService(db)
    user = await user_service.get_user(callback.from_user.id)
    
    await callback.message.edit_text(
        get_text("main_menu", lang),
        reply_markup=kb.main_menu(lang, user.is_premium if user else False)
    )

@router.callback_query(F.data == "my_lots")
async def my_lots_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    contest_service = ContestService(db)
    contests = await contest_service.get_user_contests(callback.from_user.id, limit=10)
    
    if not contests:
        await callback.answer("Sizda hali konkurslar yo'q" if lang == "uz" else "У вас пока нет конкурсов", show_alert=True)
        return
    
    text = "📦 *Sizning konkurslaringiz:*\n\n" if lang == "uz" else "📦 *Ваши конкурсы:*\n\n"
    
    for contest in contests:
        status_emoji = {"pending": "🟡", "active": "🟢", "ended": "🔴", "cancelled": "⚫"}.get(contest.status, "🟡")
        
        text += f"{status_emoji} *{contest.title}*\n"
        text += f"   📅 {contest.start_time.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"   👥 {contest.participant_count} qatnashuvchi\n"
        text += f"   📊 {contest.view_count} ko'rishlar\n\n"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang), parse_mode="Markdown")

@router.callback_query(F.data == "analytics")
async def analytics_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    analytics_service = AnalyticsService(db)
    user_stats = await analytics_service.get_user_analytics(callback.from_user.id)
    
    text = "📊 *Sizning statistikangiz:*\n\n" if lang == "uz" else "📊 *Ваша статистика:*\n\n"
    text += f"🏆 Jami konkurslar: {user_stats.get('total_contests', 0)}\n"
    text += f"👥 Jami qatnashchilar: {user_stats.get('total_participants', 0)}\n"
    text += f"📈 Eng ko'p qatnashuvchi: {user_stats.get('max_participants', 0)}\n"
    text += f"🎯 Muvaffaqiyat darajasi: {user_stats.get('participation_rate', 0):.1f}%\n"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang), parse_mode="Markdown")

@router.callback_query(F.data == "advertising")
async def advertising_callback(callback: CallbackQuery, lang: str):
    text = "📣 *Reklama*\n\n" if lang == "uz" else "📣 *Реклама*\n\n"
    text += "Reklama joylashtirish uchun admin bilan bog'laning.\n\n" if lang == "uz" else "Для размещения рекламы свяжитесь с администратором.\n\n"
    text += "💰 Narxlar:\n• Banner - 50,000 so'm\n• Post - 100,000 so'm\n• Video - 150,000 so'm"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang), parse_mode="Markdown")

@router.callback_query(F.data == "my_channels")
async def my_channels_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    channel_service = ChannelService(db)
    channels = await channel_service.get_user_channels(callback.from_user.id)
    
    if not channels:
        text = "📺 Sizda hali kanallar yo'q.\n\nKanal qo'shish uchun konkurs yarating." if lang == "uz" else "📺 У вас пока нет каналов.\n\nДля добавления канала создайте конкурс."
    else:
        text = "📺 *Sizning kanallaringiz:*\n\n" if lang == "uz" else "📺 *Ваши каналы:*\n\n"
        for channel in channels:
            text += f"• {channel['title']}\n"
            text += f"  👥 {channel.get('member_count', 0)} a'zo\n"
            if channel.get('username'):
                text += f"  🔗 @{channel['username']}\n"
            text += "\n"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang), parse_mode="Markdown")

@router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery, lang: str):
    text = "🛟 *Yordam*\n\n" if lang == "uz" else "🛟 *Поддержка*\n\n"
    text += "Savollaringiz bo'lsa, admin bilan bog'laning:\n\n" if lang == "uz" else "По всем вопросам обращайтесь к администратору:\n\n"
    text += "📧 Email: support@konkursbot.uz\n"
    text += "💬 Telegram: @konkurs_support\n"
    text += "🕐 Ish vaqti: 9:00-18:00"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang), parse_mode="Markdown")

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("Ruxsat yo'q" if lang == "uz" else "Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        get_text("admin_panel", lang),
        reply_markup=kb.admin_panel(lang)
    )
