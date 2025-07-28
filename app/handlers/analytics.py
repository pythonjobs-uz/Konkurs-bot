from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import AnalyticsService
from app.keyboards.inline import kb

router = Router()

@router.callback_query(F.data == "analytics")
async def analytics_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    analytics_service = AnalyticsService(db)
    user_analytics = await analytics_service.get_user_analytics(callback.from_user.id)
    
    text = f"""📊 *Sizning statistikangiz:*

🏆 **Konkurslar:**
• Jami yaratilgan: {user_analytics.get('total_contests', 0)}
• Faol: {user_analytics.get('active_contests', 0)}
• Tugagan: {user_analytics.get('completed_contests', 0)}
• Bekor qilingan: {user_analytics.get('cancelled_contests', 0)}

👥 **Qatnashchilar:**
• Jami: {user_analytics.get('total_participants', 0)}
• O'rtacha: {user_analytics.get('avg_participants', 0):.1f}
• Eng ko'p: {user_analytics.get('max_participants', 0)}
• Eng kam: {user_analytics.get('min_participants', 0)}

📈 **Samaradorlik:**
• Ko'rishlar: {user_analytics.get('total_views', 0)}
• CTR: {user_analytics.get('ctr', 0):.2f}%
• Qatnashish darajasi: {user_analytics.get('participation_rate', 0):.1f}%

📅 **Vaqt bo'yicha:**
• Bu oy: {user_analytics.get('this_month_contests', 0)}
• O'tgan oy: {user_analytics.get('last_month_contests', 0)}
• O'sish: {user_analytics.get('growth_rate', 0):+.1f}%""" if lang == "uz" else f"""📊 *Ваша статистика:*

🏆 **Конкурсы:**
• Всего создано: {user_analytics.get('total_contests', 0)}
• Активных: {user_analytics.get('active_contests', 0)}
• Завершенных: {user_analytics.get('completed_contests', 0)}
• Отмененных: {user_analytics.get('cancelled_contests', 0)}

👥 **Участники:**
• Всего: {user_analytics.get('total_participants', 0)}
• В среднем: {user_analytics.get('avg_participants', 0):.1f}
• Максимум: {user_analytics.get('max_participants', 0)}
• Минимум: {user_analytics.get('min_participants', 0)}

📈 **Эффективность:**
• Просмотры: {user_analytics.get('total_views', 0)}
• CTR: {user_analytics.get('ctr', 0):.2f}%
• Уровень участия: {user_analytics.get('participation_rate', 0):.1f}%

📅 **По времени:**
• Этот месяц: {user_analytics.get('this_month_contests', 0)}
• Прошлый месяц: {user_analytics.get('last_month_contests', 0)}
• Рост: {user_analytics.get('growth_rate', 0):+.1f}%"""
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(lang))
