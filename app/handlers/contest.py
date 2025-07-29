import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.core.database import db
from app.keyboards.inline import *
from app.locales.translations import get_text
from app.services.contest_service import ContestService
from app.services.user_service import UserService
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()

class ContestCreation(StatesGroup):
    waiting_for_channel = State()
    waiting_for_image = State()
    waiting_for_description = State()
    waiting_for_prize_description = State()
    waiting_for_requirements = State()
    waiting_for_button_text = State()
    waiting_for_winners_count = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_channel_selection = State()

async def check_subscription(user_id: int, channel_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

@router.callback_query(F.data == "create_contest")
async def create_contest_callback(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    is_premium = await UserService.check_premium_status(callback.from_user.id)
    
    if not is_premium:
        user_contests = await db.get_user_contests(callback.from_user.id)
        if len(user_contests) >= 3:
            await callback.message.edit_text(
                get_text("premium_required", lang),
                reply_markup=premium_keyboard(lang),
                parse_mode="Markdown"
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
        get_text("send_prize_description", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_prize_description)

@router.message(ContestCreation.waiting_for_prize_description)
async def process_prize_description(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await state.update_data(prize_description=message.text)
    await message.answer(
        get_text("send_requirements", lang),
        reply_markup=cancel_creation_keyboard(lang),
        parse_mode="Markdown"
    )
    await state.set_state(ContestCreation.waiting_for_requirements)

@router.message(ContestCreation.waiting_for_requirements)
async def process_requirements(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    await state.update_data(requirements=message.text)
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
    
    contest_id = await ContestService.create_contest(
        owner_id=callback.from_user.id,
        channel_id=channel_id,
        title=f"Konkurs #{datetime.now().strftime('%Y%m%d%H%M')}",
        description=contest_data["description"],
        image_file_id=contest_data.get("image_file_id"),
        participate_button_text=contest_data["button_text"],
        winners_count=contest_data["winners_count"],
        start_time=contest_data["start_time"],
        end_time=contest_data.get("end_time"),
        max_participants=contest_data.get("max_participants"),
        prize_description=contest_data.get("prize_description"),
        requirements=contest_data.get("requirements")
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
    
    is_premium = await UserService.check_premium_status(callback.from_user.id)
    
    await callback.message.edit_text(
        get_text("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, is_premium)
    )

@router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    contest_id = int(callback.data.split(":")[1])
    
    contest = await ContestService.get_contest_with_cache(contest_id)
    if not contest or contest['status'] != "active":
        await callback.answer(get_text("contest_ended", lang), show_alert=True)
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
    
    success = await ContestService.join_contest(contest_id, callback.from_user.id)
    
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
        await callback.answer(get_text("already_participating", lang), show_alert=True)

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

@router.callback_query(F.data.startswith("contest_stats:"))
async def contest_stats_callback(callback: CallbackQuery):
    contest_id = int(callback.data.split(":")[1])
    user = await db.get_user(callback.from_user.id)
    lang = user.get('language_code', 'uz') if user else 'uz'
    
    stats = await ContestService.get_contest_statistics(contest_id)
    
    if not stats:
        await callback.answer("Konkurs topilmadi!" if lang == "uz" else "Конкурс не найден!", show_alert=True)
        return
    
    contest = stats['contest']
    text = f"📊 *{contest['title']} - Statistika*\n\n"
    text += f"👥 Qatnashchilar: {stats['participants_count']}\n"
    text += f"📈 Ko'rishlar: {contest.get('view_count', 0)}\n"
    text += f"🏆 G'oliblar: {contest['winners_count']}\n"
    text += f"📊 Status: {contest['status'].title()}\n"
    
    if contest['start_time']:
        start_time = datetime.fromisoformat(contest['start_time'].replace('Z', '+00:00'))
        text += f"⏰ Boshlangan: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
    
    if contest['end_time']:
        end_time = datetime.fromisoformat(contest['end_time'].replace('Z', '+00:00'))
        text += f"🏁 Tugaydi: {end_time.strftime('%d.%m.%Y %H:%M')}\n"
    
    await callback.answer(text, show_alert=True)
