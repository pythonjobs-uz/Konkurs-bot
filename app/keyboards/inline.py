from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional, Dict, Any

from app.locales.translations import get_text

class KeyboardBuilder:
    @staticmethod
    def main_menu(lang: str = "uz", is_premium: bool = False) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("create_lot", lang),
                callback_data="create_lot"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("my_lots", lang),
                callback_data="my_lots"
            ),
            InlineKeyboardButton(
                text=get_text("analytics", lang),
                callback_data="analytics"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("my_channels", lang),
                callback_data="my_channels"
            ),
            InlineKeyboardButton(
                text=get_text("advertising", lang),
                callback_data="advertising"
            )
        )
        
        if not is_premium:
            builder.row(
                InlineKeyboardButton(
                    text=get_text("premium", lang),
                    callback_data="premium"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("support", lang),
                callback_data="support"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def subscription_check(lang: str = "uz", channel_url: str = None) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        if channel_url:
            builder.row(
                InlineKeyboardButton(
                    text="📢 Kanalga o'tish" if lang == "uz" else "📢 Перейти в канал",
                    url=channel_url
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("check_subscription", lang),
                callback_data="check_subscription"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def contest_participation(contest_id: int, participants_count: int, button_text: str, is_ended: bool = False) -> InlineKeyboardMarkup:
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
    
    @staticmethod
    def channel_selection(channels: List[Dict], lang: str = "uz") -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        for channel in channels:
            builder.row(
                InlineKeyboardButton(
                    text=f"📺 {channel['title']} ({channel.get('member_count', 0)})",
                    callback_data=f"select_channel:{channel['channel_id']}"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
                callback_data="main_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def admin_panel(lang: str = "uz") -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("broadcast_message", lang),
                callback_data="admin_broadcast"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("user_statistics", lang),
                callback_data="admin_stats"
            ),
            InlineKeyboardButton(
                text=get_text("system_health", lang),
                callback_data="admin_health"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("manage_channels", lang),
                callback_data="admin_channels"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
                callback_data="main_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def pagination(current_page: int, total_pages: int, callback_prefix: str, lang: str = "uz") -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        buttons = []
        
        if current_page > 1:
            buttons.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"{callback_prefix}:{current_page - 1}"
                )
            )
        
        buttons.append(
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if current_page < total_pages:
            buttons.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"{callback_prefix}:{current_page + 1}"
                )
            )
        
        builder.row(*buttons)
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
                callback_data="main_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def contest_management(contest_id: int, status: str, lang: str = "uz") -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        if status == "pending":
            builder.row(
                InlineKeyboardButton(
                    text="▶️ Boshlash" if lang == "uz" else "▶️ Запустить",
                    callback_data=f"start_contest:{contest_id}"
                )
            )
        elif status == "active":
            builder.row(
                InlineKeyboardButton(
                    text="⏹ To'xtatish" if lang == "uz" else "⏹ Остановить",
                    callback_data=f"stop_contest:{contest_id}"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Statistika" if lang == "uz" else "📊 Статистика",
                callback_data=f"contest_stats:{contest_id}"
            ),
            InlineKeyboardButton(
                text="👥 Qatnashchilar" if lang == "uz" else "👥 Участники",
                callback_data=f"contest_participants:{contest_id}"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🗑 O'chirish" if lang == "uz" else "🗑 Удалить",
                callback_data=f"delete_contest:{contest_id}"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def premium_features(lang: str = "uz") -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="💳 Premium sotib olish" if lang == "uz" else "💳 Купить Premium",
                callback_data="buy_premium"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="ℹ️ Batafsil" if lang == "uz" else "ℹ️ Подробнее",
                callback_data="premium_info"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
                callback_data="main_menu"
            )
        )
        
        return builder.as_markup()

kb = KeyboardBuilder()
