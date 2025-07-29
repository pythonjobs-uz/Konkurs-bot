import asyncio
import random
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import logging

from database import db
from keyboards import *
from translations import get_text
from config import settings

logger = logging.getLogger(__name__)

router = Router()

class ContestCreation(StatesGroup):
    waiting_for_channel = State()
    waiting_for_image = State()
    waiting_for_description = State()
    waiting_for_button_text = State()
    waiting_for_winners_count = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_channel_selection = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

async def check_subscription(user_id: int, channel_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except (TelegramBadRequest, Exception):
        return False

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    
    user = await db.create_or_update_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code if message.from_user.language_code in ["uz", "ru"] else "uz"
    )
    
    lang = user.get('language_code', 'uz')
    
    await message.answer(
        get_text("welcome", lang),
        parse_mode="Markdown"
    )
    
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
    
    await message.answer(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, user.get('is_premium', False))
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
            await callback.message.edit_text(
                get_text("subscription_confirmed", lang),
                reply_markup=main_menu_keyboard(lang, user.get('is_premium', False) if user else False),
                parse_mode="Markdown"
            )
        else:
            await callback.answer(
                get_text("subscription_required", lang),
                show_alert=True
            )
    else:
        await callback.message.edit_text(
            get_text("main_menu", lang),
            reply_markup=main_menu_keyboard(lang, user.get('is_premium', False) if user else False)
        )

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await callback.message.edit_text(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, user.get('is_premium', False) if user else False)
    )

@router.callback_query(F.data == "create_contest")
async def create_contest_callback(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    if not user.get('is_premium', False):
        user_contests = await db.get_user_contests(callback.from_user.id)
        if len(user_contests) >= 3:
            await callback.message.edit_text(
                "⚠️ Bepul foydalanuvchilar faqat 3 ta konkurs yarata oladi.\n\nPremium sotib oling!" if lang == "uz" else "⚠️ Бесплатные пользователи могут создать только 3 конкурса.\n\nКупите Premium!",
                reply_markup=back_to_menu_keyboard(lang)
            )
            return
    
    await callback.message.edit_text(
        get_text("add_channel_first", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_channel)

@router.message(ContestCreation.waiting_for_channel)
async def process_channel(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    try:
        channel_input = message.text.strip()
        
        if channel_input.startswith('@'):
            channel_username = channel_input[1:]
            channel_info = await message.bot.get_chat(f"@{channel_username}")
        elif channel_input.lstrip('-').isdigit():
            channel_id = int(channel_input)
            channel_info = await message.bot.get_chat(channel_id)
        else:
            await message.answer(
                get_text("invalid_format", lang),
                reply_markup=cancel_creation_keyboard(lang)
            )
            return
        
        bot_member = await message.bot.get_chat_member(channel_info.id, message.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                get_text("channel_not_found", lang),
                reply_markup=cancel_creation_keyboard(lang)
            )
            return
        
        try:
            member_count = await message.bot.get_chat_member_count(channel_info.id)
        except:
            member_count = 0
        
        await db.add_channel(
            channel_id=channel_info.id,
            title=channel_info.title,
            username=channel_info.username,
            owner_id=message.from_user.id,
            member_count=member_count
        )
        
        await state.update_data(selected_channel_id=channel_info.id)
        
        await message.answer(get_text("channel_added", lang))
        await message.answer(
            get_text("send_contest_image", lang),
            reply_markup=cancel_creation_keyboard(lang),
            parse_mode="Markdown"
        )
        await state.set_state(ContestCreation.waiting_for_image)
        
    except Exception as e:
        logger.error(f"Error processing channel: {e}")
        await message.answer(
            get_text("channel_not_found", lang),
            reply_markup=cancel_creation_keyboard(lang)
        )

@router.message(ContestCreation.waiting_for_image, F.photo)
async def process_image(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await state.update_data(image_file_id=message.photo[-1].file_id)
    await message.answer(
        get_text("send_description", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_description)

@router.message(ContestCreation.waiting_for_image)
async def process_no_image(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await state.update_data(image_file_id=None)
    await message.answer(
        get_text("send_description", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_description)

@router.message(ContestCreation.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    if len(message.text) > 1000:
        await message.answer(
            "Tavsif juda uzun! 1000 belgidan kam bo'lishi kerak." if lang == "uz" else "Описание слишком длинное! Должно быть менее 1000 символов.",
            reply_markup=cancel_creation_keyboard(lang)
        )
        return
    
    await state.update_data(description=message.text)
    await message.answer(
        get_text("participate_button_text", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_button_text)

@router.message(ContestCreation.waiting_for_button_text)
async def process_button_text(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    if len(message.text) > 50:
        await message.answer(
            "Tugma matni juda uzun!" if lang == "uz" else "Текст кнопки слишком длинный!",
            reply_markup=cancel_creation_keyboard(lang)
        )
        return
    
    await state.update_data(button_text=message.text)
    await message.answer(
        get_text("winners_count", lang, max_winners=settings.MAX_WINNERS_COUNT),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_winners_count)

@router.message(ContestCreation.waiting_for_winners_count)
async def process_winners_count(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    try:
        winners_count = int(message.text)
        if winners_count < 1 or winners_count > settings.MAX_WINNERS_COUNT:
            raise ValueError
        
        await state.update_data(winners_count=winners_count)
        await message.answer(
            get_text("start_time", lang),
            reply_markup=cancel_creation_keyboard(lang),
            parse_mode="Markdown"
        )
        await state.set_state(ContestCreation.waiting_for_start_time)
        
    except ValueError:
        await message.answer(
            get_text("invalid_format", lang),
            reply_markup=cancel_creation_keyboard(lang)
        )

@router.message(ContestCreation.waiting_for_start_time)
async def process_start_time(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    try:
        start_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        
        if start_time < datetime.now():
            await message.answer(
                "Boshlanish vaqti hozirgi vaqtdan keyin bo'lishi kerak!" if lang == "uz" else "Время начала должно быть в будущем!",
                reply_markup=cancel_creation_keyboard(lang)
            )
            return
        
        if start_time > datetime.now() + timedelta(days=settings.MAX_CONTEST_DURATION_DAYS):
            await message.answer(
                f"Konkurs {settings.MAX_CONTEST_DURATION_DAYS} kundan ko'p davom eta olmaydi!" if lang == "uz" else f"Конкурс не может длиться более {settings.MAX_CONTEST_DURATION_DAYS} дней!",
                reply_markup=cancel_creation_keyboard(lang)
            )
            return
        
        await state.update_data(start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"))
        await message.answer(
            get_text("end_time", lang),
            reply_markup=cancel_creation_keyboard(lang),
            parse_mode="Markdown"
        )
        await state.set_state(ContestCreation.waiting_for_end_time)
        
    except ValueError:
        await message.answer(
            get_text("invalid_format", lang),
            reply_markup=cancel_creation_keyboard(lang)
        )

@router.message(ContestCreation.waiting_for_end_time)
async def process_end_time(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    try:
        contest_data = await state.get_data()
        start_time = datetime.strptime(contest_data["start_time"], "%Y-%m-%d %H:%M:%S")
        
        try:
            end_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
            if end_time <= start_time:
                await message.answer(
                    "Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak!" if lang == "uz" else "Время окончания должно быть после времени начала!",
                    reply_markup=cancel_creation_keyboard(lang)
                )
                return
            await state.update_data(end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"), max_participants=None)
        except ValueError:
            max_participants = int(message.text)
            if max_participants < 1 or max_participants > settings.MAX_PARTICIPANTS:
                raise ValueError
            await state.update_data(end_time=None, max_participants=max_participants)
        
        channels = await db.get_user_channels(message.from_user.id)
        
        if not channels:
            await message.answer(
                "Sizda kanallar yo'q!" if lang == "uz" else "У вас нет каналов!",
                reply_markup=back_to_menu_keyboard(lang)
            )
            await state.clear()
            return
        
        await message.answer(
            get_text("select_channel", lang),
            reply_markup=channel_selection_keyboard(channels, lang),
            parse_mode="Markdown"
        )
        await state.set_state(ContestCreation.waiting_for_channel_selection)
        
    except ValueError:
        await message.answer(
            get_text("invalid_format", lang),
            reply_markup=cancel_creation_keyboard(lang)
        )

@router.callback_query(F.data.startswith("select_channel:"), ContestCreation.waiting_for_channel_selection)
async def process_channel_selection(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    channel_id = int(callback.data.split(":")[1])
    contest_data = await state.get_data()
    
    contest_id = await db.create_contest(
        owner_id=callback.from_user.id,
        channel_id=channel_id,
        title=f"Konkurs #{datetime.now().strftime('%Y%m%d%H%M')}",
        description=contest_data["description"],
        image_file_id=contest_data.get("image_file_id"),
        participate_button_text=contest_data["button_text"],
        winners_count=contest_data["winners_count"],
        start_time=contest_data["start_time"],
        end_time=contest_data.get("end_time"),
        max_participants=contest_data.get("max_participants")
    )
    
    await callback.message.edit_text(
        get_text("contest_created", lang),
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "cancel_creation")
async def cancel_creation_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await callback.message.edit_text(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, user.get('is_premium', False) if user else False)
    )

@router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    contest_id = int(callback.data.split(":")[1])
    
    contest = await db.get_contest(contest_id)
    if not contest or contest['status'] != "active":
        await callback.answer(get_text("contest_ended", lang), show_alert=True)
        return
    
    is_participating = await db.is_participating(contest_id, callback.from_user.id)
    if is_participating:
        await callback.answer(get_text("already_participating", lang), show_alert=True)
        return
    
    if contest['max_participants']:
        current_participants = await db.get_participants_count(contest_id)
        if current_participants >= contest['max_participants']:
            await callback.answer("Konkurs to'ldi!" if lang == "uz" else "Конкурс заполнен!", show_alert=True)
            return
    
    if settings.SPONSOR_CHANNEL_ID:
        if not await check_subscription(callback.from_user.id, settings.SPONSOR_CHANNEL_ID, callback.bot):
            await callback.answer(get_text("not_subscribed", lang), show_alert=True)
            return
    
    success = await db.add_participant(contest_id, callback.from_user.id)
    if success:
        participants_count = await db.get_participants_count(contest_id)
        new_keyboard = contest_participation_keyboard(
            contest_id, participants_count, contest['participate_button_text']
        )
        
        try:
            await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        except:
            pass
        
        await callback.answer(get_text("participation_confirmed", lang), show_alert=True)
    else:
        await callback.answer(get_text("error_occurred", lang), show_alert=True)

@router.callback_query(F.data == "my_contests")
async def my_contests_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    contests = await db.get_user_contests(callback.from_user.id, limit=10)
    
    if not contests:
        await callback.answer(
            "Sizda hali konkurslar yo'q" if lang == "uz" else "У вас пока нет конкурсов", 
            show_alert=True
        )
        return
    
    text = "📦 *Sizning konkurslaringiz:*\n\n" if lang == "uz" else "📦 *Ваши конкурсы:*\n\n"
    
    for contest in contests:
        status_emoji = {"pending": "🟡", "active": "🟢", "ended": "🔴", "cancelled": "⚫"}.get(contest['status'], "🟡")
        
        text += f"{status_emoji} *{contest['title']}*\n"
        if contest['start_time']:
            start_time = datetime.fromisoformat(contest['start_time'].replace('Z', '+00:00'))
            text += f"   📅 {start_time.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"   👥 {contest['participant_count']} qatnashuvchi\n"
        text += f"   📊 {contest['view_count']} ko'rishlar\n\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "analytics")
async def analytics_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    user_contests = await db.get_user_contests(callback.from_user.id)
    
    total_contests = len(user_contests)
    active_contests = len([c for c in user_contests if c['status'] == "active"])
    total_participants = sum(c['participant_count'] for c in user_contests)
    total_views = sum(c['view_count'] for c in user_contests)
    
    text = "📊 *Sizning statistikangiz:*\n\n" if lang == "uz" else "📊 *Ваша статистика:*\n\n"
    text += f"🏆 Jami konkurslar: {total_contests}\n"
    text += f"🟢 Faol konkurslar: {active_contests}\n"
    text += f"👥 Jami qatnashchilar: {total_participants}\n"
    text += f"📈 Jami ko'rishlar: {total_views}\n"
    
    if total_contests > 0:
        avg_participants = total_participants / total_contests
        text += f"📊 O'rtacha qatnashchilar: {avg_participants:.1f}\n"
    
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
            text += f"• {channel['title']}\n"
            text += f"  👥 {channel.get('member_count', 0)} a'zo\n"
            if channel.get('username'):
                text += f"  🔗 @{channel['username']}\n"
            text += "\n"
    
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
    text += "Savollaringiz bo'lsa, admin bilan bog'laning:\n\n" if lang == "uz" else "По всем вопросам обращайтесь к администратору:\n\n"
    text += "📧 Email: support@konkursbot.uz\n"
    text += "💬 Telegram: @konkurs_support\n"
    text += "🕐 Ish vaqti: 9:00-18:00"
    
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
    text += "🚀 Qo'shimcha funksiyalar:\n• Cheksiz konkurslar\n• Kengaytirilgan statistika\n• Maxsus dizayn\n• Prioritet qo'llab-quvvatlash\n\n" if lang == "uz" else "🚀 Дополнительные функции:\n• Неограниченные конкурсы\n• Расширенная аналитика\n• Особый дизайн\n• Приоритетная поддержка\n\n"
    text += "💰 Narx: 50,000 so'm/oy" if lang == "uz" else "💰 Цена: 50,000 сум/месяц"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    text = "⚙️ *Sozlamalar*\n\n" if lang == "uz" else "⚙️ *Настройки*\n\n"
    text += f"🌐 Til: {'O\'zbekcha' if lang == 'uz' else 'Русский'}\n"
    text += f"⭐ Status: {'Premium' if user and user.get('is_premium') else 'Oddiy'}\n"
    if user and user.get('created_at'):
        created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
        text += f"📅 Ro'yxatdan o'tgan: {created_at.strftime('%d.%m.%Y')}"
    
    await callback.message.edit_text(
        text, 
        reply_markup=back_to_menu_keyboard(lang), 
        parse_mode="Markdown"
    )

@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    stats = await db.get_statistics()
    
    text = "👨‍💻 *Admin Panel*\n\n"
    text += f"📊 Statistika:\n"
    text += f"• Jami foydalanuvchilar: {stats['total_users']}\n"
    text += f"• Faol foydalanuvchilar: {stats['active_users']}\n"
    text += f"• Jami konkurslar: {stats['total_contests']}\n"
    text += f"• Faol konkurslar: {stats['active_contests']}\n"
    text += f"• Jami qatnashchilar: {stats['total_participants']}\n"
    
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
        "📢 *Reklama xabarini yuboring:*" if lang == "uz" else "📢 *Отправьте рекламное сообщение:*",
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
    
    users = await db.get_all_active_users()
    success_count = 0
    
    for user_data in users:
        try:
            await message.send_copy(chat_id=user_data['id'])
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
    
    await message.answer(
        f"✅ *Reklama yuborildi!*\n\n📊 Muvaffaqiyatli: {success_count} foydalanuvchi" if lang == "uz" else f"✅ *Реклама отправлена!*\n\n📊 Успешно: {success_count} пользователей",
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
    
    text = "📊 *Tizim statistikasi:*\n\n" if lang == "uz" else "📊 *Системная статистика:*\n\n"
    text += f"👥 **Foydalanuvchilar:**\n"
    text += f"• Jami: {stats['total_users']}\n"
    text += f"• Faol: {stats['active_users']}\n\n"
    text += f"🏆 **Konkurslar:**\n"
    text += f"• Jami: {stats['total_contests']}\n"
    text += f"• Faol: {stats['active_contests']}\n\n"
    text += f"👥 **Qatnashchilar:**\n"
    text += f"• Jami: {stats['total_participants']}\n"
    
    await callback.message.edit_text(
        text, 
        reply_markup=admin_panel_keyboard(lang), 
        parse_mode="Markdown"
    )

async def select_winners(contest_id: int, winners_count: int) -> list:
    participants = await db.get_contest_participants(contest_id)
    
    if not participants:
        return []
    
    winners_count = min(winners_count, len(participants))
    selected_winners = random.sample(participants, winners_count)
    
    for i, winner in enumerate(selected_winners, 1):
        await db.create_winner(contest_id, winner['id'], i)
    
    return selected_winners

async def check_contests_scheduler():
    while True:
        try:
            contests = await db.get_active_contests()
            
            for contest in contests:
                now = datetime.now()
                
                if contest['status'] == 'pending' and contest['start_time']:
                    start_time = datetime.fromisoformat(contest['start_time'].replace('Z', '+00:00'))
                    if start_time <= now:
                        await start_contest(contest)
                
                elif contest['status'] == 'active':
                    should_end = False
                    
                    if contest['end_time']:
                        end_time = datetime.fromisoformat(contest['end_time'].replace('Z', '+00:00'))
                        if end_time <= now:
                            should_end = True
                    
                    elif contest['max_participants']:
                        current_participants = await db.get_participants_count(contest['id'])
                        if current_participants >= contest['max_participants']:
                            should_end = True
                    
                    if should_end:
                        await end_contest(contest)
            
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in contest scheduler: {e}")
            await asyncio.sleep(60)

async def start_contest(contest):
    try:
        from main import bot_instance
        
        text = f"🎉 <b>{contest['title']}</b>\n\n{contest['description']}"
        text += f"\n\n🏆 G'oliblar: {contest['winners_count']} kishi"
        
        if contest['end_time']:
            end_time = datetime.fromisoformat(contest['end_time'].replace('Z', '+00:00'))
            text += f"\n⏰ Tugash: {end_time.strftime('%d.%m.%Y %H:%M')}"
        elif contest['max_participants']:
            text += f"\n👥 Maksimal qatnashchilar: {contest['max_participants']}"
        
        keyboard = contest_participation_keyboard(
            contest['id'], 0, contest['participate_button_text']
        )
        
        if contest['image_file_id']:
            message = await bot_instance.send_photo(
                chat_id=contest['channel_id'],
                photo=contest['image_file_id'],
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            message = await bot_instance.send_message(
                chat_id=contest['channel_id'],
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await db.update_contest_status(contest['id'], 'active')
        await db.set_contest_message_id(contest['id'], message.message_id)
        
        logger.info(f"Started contest {contest['id']}")
        
    except Exception as e:
        logger.error(f"Failed to start contest {contest['id']}: {e}")

async def end_contest(contest):
    try:
        from main import bot_instance
        
        winners = await select_winners(contest['id'], contest['winners_count'])
        
        if winners:
            winners_text = "🏆 <b>G'oliblar e'lon qilindi:</b>\n\n"
            
            for i, winner in enumerate(winners, 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
                winners_text += f"{emoji} <b>{i}-o'rin:</b> <a href='tg://user?id={winner['id']}'>{winner.get('first_name', 'User')}</a>\n"
            
            winners_text += f"\n🎉 Tabriklaymiz! Adminlar siz bilan bog'lanadi."
            
            await bot_instance.send_message(
                chat_id=contest['channel_id'],
                text=winners_text,
                parse_mode="HTML"
            )
            
            for winner in winners:
                try:
                    await bot_instance.send_message(
                        chat_id=winner['id'],
                        text=f"🎉 <b>Tabriklaymiz!</b>\n\nSiz <b>{contest['title']}</b> konkursida g'olib bo'ldingiz!\n\nTez orada admin siz bilan bog'lanadi.",
                        parse_mode="HTML"
                    )
                except:
                    pass
        
        await db.update_contest_status(contest['id'], 'ended')
        logger.info(f"Ended contest {contest['id']} with {len(winners)} winners")
        
    except Exception as e:
        logger.error(f"Failed to end contest {contest['id']}: {e}")
