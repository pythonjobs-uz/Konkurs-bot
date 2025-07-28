from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.keyboards.inline import kb
from app.locales.translations import get_text
from app.core.config import settings
from app.core.metrics import metrics

router = Router()

@router.message(CommandStart())
async def start_command(message: Message, db: AsyncSession, lang: str):
    user_service = UserService(db)
    subscription_service = SubscriptionService()
    
    user = await user_service.create_or_update_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=lang
    )
    
    metrics.record_user_action("start")
    
    await message.answer_photo(
        photo=settings.WELCOME_IMAGE_URL,
        caption=get_text("welcome", lang),
        reply_markup=None
    )
    
    if settings.SPONSOR_CHANNEL_ID:
        is_subscribed = await subscription_service.check_subscription(
            message.from_user.id, settings.SPONSOR_CHANNEL_ID
        )
        
        if not is_subscribed:
            channel_url = f"https://t.me/{settings.SPONSOR_CHANNEL_USERNAME}" if settings.SPONSOR_CHANNEL_USERNAME else None
            await message.answer_photo(
                photo=settings.SPONSOR_IMAGE_URL,
                caption=get_text("subscribe_sponsor", lang),
                reply_markup=kb.subscription_check(lang, channel_url)
            )
            return
    
    await message.answer(
        get_text("main_menu", lang),
        reply_markup=kb.main_menu(lang, user.is_premium)
    )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    subscription_service = SubscriptionService()
    user_service = UserService(db)
    
    if settings.SPONSOR_CHANNEL_ID:
        is_subscribed = await subscription_service.check_subscription(
            callback.from_user.id, settings.SPONSOR_CHANNEL_ID
        )
        
        if is_subscribed:
            user = await user_service.get_user(callback.from_user.id)
            await callback.message.edit_text(
                get_text("subscription_confirmed", lang),
                reply_markup=kb.main_menu(lang, user.is_premium if user else False)
            )
        else:
            await callback.answer(
                get_text("subscription_required", lang),
                show_alert=True
            )
    else:
        user = await user_service.get_user(callback.from_user.id)
        await callback.message.edit_text(
            get_text("main_menu", lang),
            reply_markup=kb.main_menu(lang, user.is_premium if user else False)
        )
