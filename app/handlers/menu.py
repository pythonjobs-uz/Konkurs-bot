from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.core.database import db
from app.keyboards.inline import *
from app.locales.translations import get_text
from app.services.user_service import UserService
from app.services.analytics_service import AnalyticsService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "analytics")
async def analytics_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    analytics = await UserService.get_user_analytics(callback.from_user.id)
    
    text = "📊 *Sizning statistikangiz:*\n\n" if lang == "uz" else "📊 *Ваша статистика:*\n\n"
    text += f"🏆 Yaratgan konkurslar: {analytics['contests_created']}\n"
    text += f"👥 Jami qatnashchilar: {analytics['total_participants']}\n"
    text += f"🎯 Qatnashgan konkurslar: {analytics['participated_contests']}\n"
    text += f"🥇 Yutgan konkurslar: {analytics['won_contests']}\n"
    text += f"📈 Muvaffaqiyat darajasi: {analytics['success_rate']:.1f}%\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "my_channels")
async def my_channels_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    channels = await db.get_user_channels(callback.from_user.id)
    
    if not channels:
        text = "📺 Sizda hali kanallar yo'q.\n\nKanal qo'shish uchun konkurs yarating." if lang == "uz" else "📺 У вас пока нет каналов.\n\nДля добавления канала создайте конкурс."
    else:
        text = "📺 *Sizning kanallaringiz:*\n\n" if lang == "uz" else "📺 *Ваши каналы:*\n\n"
        for channel in channels:
            verified_emoji = "✅" if channel.get('is_verified') else ""
            text += f"• {channel['title']} {verified_emoji}\n"
            text += f"  👥 {channel.get('member_count', 0)} a'zo\n"
            if channel.get('username'):
                text += f"  🔗 @{channel['username']}\n"
            text += "\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "referral")
async def referral_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    referral_info = await UserService.get_referral_info(callback.from_user.id)
    
    text = get_text("referral_info", lang, 
                   referral_link=referral_info['referral_link'],
                   referrals_count=referral_info['referrals_count'],
                   bonus_amount=referral_info['bonus_amount'])
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "notifications")
async def notifications_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    notifications = await db.get_user_notifications(callback.from_user.id)
    
    if not notifications:
        text = get_text("no_notifications", lang)
    else:
        text = get_text("notifications", lang) + "\n\n"
        for notification in notifications[:5]:
            status_emoji = "🔴" if not notification['is_read'] else "✅"
            created_at = datetime.fromisoformat(notification['created_at'].replace('Z', '+00:00'))
            text += f"{status_emoji} *{notification['title']}*\n"
            text += f"   {notification['message'][:50]}...\n"
            text += f"   📅 {created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    is_premium = await UserService.check_premium_status(callback.from_user.id)
    
    text = "⚙️ *Sozlamalar*\n\n" if lang == "uz" else "⚙️ *Настройки*\n\n"
    text += f"🌐 Til: {'O\'zbekcha' if lang == 'uz' else 'Русский'}\n"
    text += f"⭐ Status: {'Premium' if is_premium else 'Oddiy'}\n"
    text += f"🆔 ID: {user['id']}\n"
    
    if user and user.get('created_at'):
        created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
        text += f"📅 Ro'yxatdan o'tgan: {created_at.strftime('%d.%m.%Y')}\n"
    
    if is_premium and user.get('premium_until'):
        premium_until = datetime.fromisoformat(user['premium_until'])
        text += f"⏰ Premium tugaydi: {premium_until.strftime('%d.%m.%Y')}\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "premium")
async def premium_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    text = "⭐ *Premium Imkoniyatlar*\n\n" if lang == "uz" else "⭐ *Премиум возможности*\n\n"
    text += "🚀 Qo'shimcha funksiyalar:\n" if lang == "uz" else "🚀 Дополнительные функции:\n"
    text += "• Cheksiz konkurslar\n" if lang == "uz" else "• Неограниченные конкурсы\n"
    text += "• Kengaytirilgan statistika\n" if lang == "uz" else "• Расширенная аналитика\n"
    text += "• Maxsus dizayn\n" if lang == "uz" else "• Особый дизайн\n"
    text += "• Prioritet qo'llab-quvvatlash\n" if lang == "uz" else "• Приоритетная поддержка\n"
    text += "• Reklama yo'q\n" if lang == "uz" else "• Без рекламы\n"
    text += "• Eksport funksiyasi\n\n" if lang == "uz" else "• Функция экспорта\n\n"
    text += f"💰 Narx: {settings.PREMIUM_PRICE:,} so'm/oy" if lang == "uz" else f"💰 Цена: {settings.PREMIUM_PRICE:,} сум/месяц"
    
    await callback.message.edit_text(
        text, 
        reply_markup=premium_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "premium_features")
async def premium_features_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    text = "✨ *Premium Funksiyalar Batafsil*\n\n" if lang == "uz" else "✨ *Премиум функции подробно*\n\n"
    
    features = [
        ("🚀", "Cheksiz konkurslar yaratish", "Неограниченное создание конкурсов"),
        ("📊", "Kengaytirilgan analitika va hisobotlar", "Расширенная аналитика и отчеты"),
        ("🎨", "Maxsus dizayn va shablon", "Особый дизайн и шаблоны"),
        ("⚡", "Tezkor qo'llab-quvvatlash", "Быстрая поддержка"),
        ("📤", "Ma'lumotlarni eksport qilish", "Экспорт данных"),
        ("🔔", "Maxsus bildirishnomalar", "Специальные уведомления"),
        ("📈", "Real-time statistika", "Статистика в реальном времени"),
        ("🎯", "Maqsadli auditoriya", "Целевая аудитория")
    ]
    
    for emoji, uz_text, ru_text in features:
        feature_text = uz_text if lang == "uz" else ru_text
        text += f"{emoji} {feature_text}\n"
    
    text += f"\n💎 Faqat {settings.PREMIUM_PRICE:,} so'm/oy!" if lang == "uz" else f"\n💎 Всего {settings.PREMIUM_PRICE:,} сум/месяц!"
    
    await callback.message.edit_text(
        text, 
        reply_markup=premium_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "buy_premium")
async def buy_premium_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    text = "💳 *Premium sotib olish*\n\n" if lang == "uz" else "💳 *Покупка Premium*\n\n"
    text += "To'lov usullari:\n\n" if lang == "uz" else "Способы оплаты:\n\n"
    text += "💳 Click/Payme\n"
    text += "🏦 Bank kartasi\n"
    text += "💰 Naqd pul\n\n"
    text += "To'lov uchun admin bilan bog'laning:\n" if lang == "uz" else "Для оплаты свяжитесь с администратором:\n"
    text += "@konkurs_admin"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    text = "🛟 *Yordam*\n\n" if lang == "uz" else "🛟 *Поддержка*\n\n"
    text += "Savollaringiz bo'lsa, biz bilan bog'laning:\n\n" if lang == "uz" else "По всем вопросам обращайтесь к нам:\n\n"
    text += "📧 Email: support@konkursbot.uz\n"
    text += "💬 Telegram: @konkurs_support\n"
    text += "📞 Telefon: +998 90 123 45 67\n"
    text += "🕐 Ish vaqti: 9:00-18:00 (Dush-Juma)" if lang == "uz" else "🕐 Рабочее время: 9:00-18:00 (Пн-Пт)"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )
