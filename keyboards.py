from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

def main_menu_keyboard(lang: str = "uz", is_premium: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    create_text = "📥 Yangi konkurs yaratish" if lang == "uz" else "📥 Создать конкурс"
    builder.row(InlineKeyboardButton(text=create_text, callback_data="create_contest"))
    
    my_contests_text = "📦 Konkurslarim" if lang == "uz" else "📦 Мои конкурсы"
    analytics_text = "📊 Statistika" if lang == "uz" else "📊 Аналитика"
    builder.row(
        InlineKeyboardButton(text=my_contests_text, callback_data="my_contests"),
        InlineKeyboardButton(text=analytics_text, callback_data="analytics")
    )
    
    channels_text = "📺 Kanallarim" if lang == "uz" else "📺 Мои каналы"
    settings_text = "⚙️ Sozlamalar" if lang == "uz" else "⚙️ Настройки"
    builder.row(
        InlineKeyboardButton(text=channels_text, callback_data="my_channels"),
        InlineKeyboardButton(text=settings_text, callback_data="settings")
    )
    
    if not is_premium:
        premium_text = "⭐ Premium" if lang == "uz" else "⭐ Премиум"
        builder.row(InlineKeyboardButton(text=premium_text, callback_data="premium"))
    
    support_text = "🛟 Yordam" if lang == "uz" else "🛟 Поддержка"
    builder.row(InlineKeyboardButton(text=support_text, callback_data="support"))
    
    return builder.as_markup()

def subscription_check_keyboard(lang: str = "uz", channel_url: str = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if channel_url:
        channel_text = "📢 Kanalga o'tish" if lang == "uz" else "📢 Перейти в канал"
        builder.row(InlineKeyboardButton(text=channel_text, url=channel_url))
    
    check_text = "✅ Obunani tekshirish" if lang == "uz" else "✅ Проверить подписку"
    builder.row(InlineKeyboardButton(text=check_text, callback_data="check_subscription"))
    
    return builder.as_markup()

def contest_participation_keyboard(contest_id: int, participants_count: int, 
                                 button_text: str, is_ended: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if not is_ended:
        builder.row(
            InlineKeyboardButton(
                text=f"{button_text} ({participants_count})",
                callback_data=f"join_contest:{contest_id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"🏁 Tugagan ({participants_count})",
                callback_data="contest_ended"
            )
        )
    
    return builder.as_markup()

def channel_selection_keyboard(channels: List[Dict], lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for channel in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"📺 {channel['title']} ({channel.get('member_count', 0)})",
                callback_data=f"select_channel:{channel['channel_id']}"
            )
        )
    
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    builder.row(InlineKeyboardButton(text=back_text, callback_data="main_menu"))
    
    return builder.as_markup()

def back_to_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    builder.row(InlineKeyboardButton(text=back_text, callback_data="main_menu"))
    return builder.as_markup()

def cancel_creation_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    cancel_text = "❌ Bekor qilish" if lang == "uz" else "❌ Отмена"
    builder.row(InlineKeyboardButton(text=cancel_text, callback_data="cancel_creation"))
    return builder.as_markup()

def admin_panel_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    broadcast_text = "📢 Reklama yuborish" if lang == "uz" else "📢 Отправить рекламу"
    builder.row(InlineKeyboardButton(text=broadcast_text, callback_data="admin_broadcast"))
    
    stats_text = "📊 Statistika" if lang == "uz" else "📊 Статистика"
    builder.row(InlineKeyboardButton(text=stats_text, callback_data="admin_stats"))
    
    back_text = "🔙 Orqaga" if lang == "uz" else "🔙 Назад"
    builder.row(InlineKeyboardButton(text=back_text, callback_data="main_menu"))
    
    return builder.as_markup()
