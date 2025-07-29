from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from app.core.database import db
from app.keyboards.inline import main_menu_keyboard, subscription_check_keyboard
from app.locales.translations import get_text
from app.services.user_service import UserService
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()

async def check_subscription(user_id: int, channel_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    
    # Handle referral
    referral_code = None
    if message.text and len(message.text.split()) > 1:
        start_param = message.text.split()[1]
        if start_param.startswith('ref_'):
            referral_code = start_param[4:]
    
    user = await db.create_or_update_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code if message.from_user.language_code in ["uz", "ru"] else "uz"
    )
    
    # Process referral if it's a new user
    if referral_code and not user.get('referred_by'):
        await UserService.process_referral(message.from_user.id, referral_code)
    
    lang = user.get('language_code', 'uz')
    
    await message.answer(
        get_text("welcome", lang),
        parse_mode="Markdown"
    )
    
    # Check sponsor subscription
    if settings.SPONSOR_CHANNEL_ID:
        is_subscribed = await check_subscription(
            message.from_user.id, settings.SPONSOR_CHANNEL_ID, message.bot
        )
        
        if not is_subscribed:
            channel_url = f"https://t.me/{settings.SPONSOR_CHANNEL_USERNAME}" if settings.SPONSOR_CHANNEL_USERNAME else None
            await message.answer(
                get_text("subscribe_sponsor", lang),
                reply_markup=subscription_check_keyboard(lang, channel_url),
                parse_mode="Markdown"
            )
            return
    
    is_premium = await UserService.check_premium_status(message.from_user.id)
    
    await message.answer(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, is_premium)
    )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    if settings.SPONSOR_CHANNEL_ID:
        is_subscribed = await check_subscription(
            callback.from_user.id, settings.SPONSOR_CHANNEL_ID, callback.bot
        )
        
        if is_subscribed:
            is_premium = await UserService.check_premium_status(callback.from_user.id)
            await callback.message.edit_text(
                get_text("subscription_confirmed", lang),
                reply_markup=main_menu_keyboard(lang, is_premium),
                parse_mode="Markdown"
            )
        else:
            await callback.answer(
                get_text("subscription_required", lang),
                show_alert=True
            )
    else:
        is_premium = await UserService.check_premium_status(callback.from_user.id)
        await callback.message.edit_text(
            get_text("main_menu", lang),
            reply_markup=main_menu_keyboard(lang, is_premium)
        )

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    is_premium = await UserService.check_premium_status(callback.from_user.id)
    
    await callback.message.edit_text(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, is_premium)
    )
