from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.keyboards.inline import kb
from app.locales.translations import get_text

router = Router()

@router.callback_query(F.data == "premium")
async def premium_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    await callback.message.edit_text(
        get_text("premium_features", lang),
        reply_markup=kb.premium_features(lang)
    )

@router.callback_query(F.data == "premium_info")
async def premium_info_callback(callback: CallbackQuery, lang: str):
    text = """⭐ *Premium Imkoniyatlar:*

🚀 **Konkurslar:**
• Cheksiz konkurslar yaratish
• Kengaytirilgan konkurs sozlamalari
• Maxsus dizayn va shablon
• Avtomatik g'oliblar e'loni

📊 **Statistika:**
• Batafsil analytics
• Export qilish imkoniyati
• Real-time monitoring
• Taqqoslash hisobotlari

🎨 **Dizayn:**
• Maxsus logotip
• Rang sxemasini sozlash
• Premium badgelar
• Brending imkoniyatlari

🛟 **Qo'llab-quvvatlash:**
• Prioritet yordam
• Shaxsiy menejer
• 24/7 texnik yordam
• Video qo'llanma

💰 **Narx:** 50,000 so'm/oy""" if lang == "uz" else """⭐ *Premium возможности:*

🚀 **Конкурсы:**
• Неограниченные конкурсы
• Расширенные настройки
• Особый дизайн и шаблоны
• Автоматическое объявление победителей

📊 **Статистика:**
• Подробная аналитика
• Возможность экспорта
• Мониторинг в реальном времени
• Сравнительные отчеты

🎨 **Дизайн:**
• Особый логотип
• Настройка цветовой схемы
• Premium значки
• Брендинг возможности

🛟 **Поддержка:**
• Приоритетная помощь
• Личный менеджер
• Техподдержка 24/7
• Видео руководство

💰 **Цена:** 50,000 сум/месяц"""
    
    await callback.message.edit_text(text, reply_markup=kb.premium_features(lang))

@router.callback_query(F.data == "buy_premium")
async def buy_premium_callback(callback: CallbackQuery, lang: str):
    text = """💳 *Premium sotib olish:*

📱 **To'lov usullari:**
• Click
• Payme
• Uzcard
• Humo
• Visa/MasterCard

📞 **Bog'lanish:**
• Telegram: @premium_support
• Telefon: +998 90 123 45 67

💡 **Qadamlar:**
1. To'lov usulini tanlang
2. 50,000 so'm to'lang
3. Chekni yuboring
4. Premium faollashtiriladi

⚡ **Tezkor faollashtirish:** 5 daqiqa ichida!""" if lang == "uz" else """💳 *Покупка Premium:*

📱 **Способы оплаты:**
• Click
• Payme
• Uzcard
• Humo
• Visa/MasterCard

📞 **Связь:**
• Telegram: @premium_support
• Телефон: +998 90 123 45 67

💡 **Шаги:**
1. Выберите способ оплаты
2. Оплатите 50,000 сум
3. Отправьте чек
4. Premium активируется

⚡ **Быстрая активация:** в течение 5 минут!"""
    
    await callback.message.edit_text(text, reply_markup=kb.premium_features(lang))
