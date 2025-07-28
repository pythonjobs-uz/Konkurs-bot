from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import re

from app.services.contest_service import ContestService
from app.services.channel_service import ChannelService
from app.services.participation_service import ParticipationService
from app.services.analytics_service import AnalyticsService
from app.keyboards.inline import kb
from app.locales.translations import get_text
from app.core.config import settings
from app.core.metrics import metrics

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
    waiting_for_prize_description = State()

@router.callback_query(F.data == "create_lot")
async def create_lot_callback(callback: CallbackQuery, state: FSMContext, db: AsyncSession, lang: str):
    user_service = UserService(db)
    user = await user_service.get_user(callback.from_user.id)
    
    if not user.is_premium:
        user_contests = await ContestService(db).get_user_contests_count(callback.from_user.id)
        if user_contests >= 3:
            await callback.message.edit_text(
                "⚠️ Bepul foydalanuvchilar faqat 3 ta konkurs yarata oladi.\n\nPremium sotib oling!" if lang == "uz" else "⚠️ Бесплатные пользователи могут создать только 3 конкурса.\n\nКупите Premium!",
                reply_markup=kb.premium_features(lang)
            )
            return
    
    await callback.message.edit_text(
        get_text("add_channel_first", lang),
        reply_markup=None
    )
    await state.set_state(ContestCreation.waiting_for_channel)

@router.message(ContestCreation.waiting_for_channel)
async def process_channel(message: Message, state: FSMContext, db: AsyncSession, lang: str):
    channel_service = ChannelService(db)
    
    try:
        channel_input = message.text.strip()
        
        if channel_input.startswith('@'):
            channel_username = channel_input[1:]
            channel_info = await message.bot.get_chat(f"@{channel_username}")
        elif channel_input.lstrip('-').isdigit():
            channel_id = int(channel_input)
            channel_info = await message.bot.get_chat(channel_id)
        else:
            await message.answer(get_text("invalid_format", lang))
            return
        
        bot_member = await message.bot.get_chat_member(channel_info.id, message.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(get_text("channel_not_found", lang))
            return
        
        member_count = await message.bot.get_chat_member_count(channel_info.id)
        
        await channel_service.add_channel(
            channel_id=channel_info.id,
            title=channel_info.title,
            username=channel_info.username,
            owner_id=message.from_user.id,
            member_count=member_count
        )
        
        await state.update_data(selected_channel_id=channel_info.id)
        
        await message.answer(get_text("channel_added", lang))
        await message.answer(get_text("send_contest_image", lang))
        await state.set_state(ContestCreation.waiting_for_image)
        
    except Exception as e:
        await message.answer(get_text("channel_not_found", lang))

@router.message(ContestCreation.waiting_for_image, F.photo)
async def process_image(message: Message, state: FSMContext, lang: str):
    await state.update_data(image_file_id=message.photo[-1].file_id)
    await message.answer(get_text("send_description", lang))
    await state.set_state(ContestCreation.waiting_for_description)

@router.message(ContestCreation.waiting_for_description)
async def process_description(message: Message, state: FSMContext, lang: str):
    if len(message.text) > 1000:
        await message.answer("Tavsif juda uzun! 1000 belgidan kam bo'lishi kerak." if lang == "uz" else "Описание слишком длинное! Должно быть менее 1000 символов.")
        return
    
    await state.update_data(description=message.text)
    await message.answer(get_text("participate_button_text", lang))
    await state.set_state(ContestCreation.waiting_for_button_text)

@router.message(ContestCreation.waiting_for_button_text)
async def process_button_text(message: Message, state: FSMContext, lang: str):
    if len(message.text) > 50:
        await message.answer("Tugma matni juda uzun!" if lang == "uz" else "Текст кнопки слишком длинный!")
        return
    
    await state.update_data(button_text=message.text)
    await message.answer(get_text("winners_count", lang, max_winners=settings.MAX_WINNERS_COUNT))
    await state.set_state(ContestCreation.waiting_for_winners_count)

@router.message(ContestCreation.waiting_for_winners_count)
async def process_winners_count(message: Message, state: FSMContext, lang: str):
    try:
        winners_count = int(message.text)
        if winners_count < 1 or winners_count > settings.MAX_WINNERS_COUNT:
            raise ValueError
        
        await state.update_data(winners_count=winners_count)
        await message.answer(get_text("start_time", lang))
        await state.set_state(ContestCreation.waiting_for_start_time)
        
    except ValueError:
        await message.answer(get_text("invalid_format", lang))

@router.message(ContestCreation.waiting_for_start_time)
async def process_start_time(message: Message, state: FSMContext, lang: str):
    try:
        start_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        
        if start_time < datetime.now():
            await message.answer("Boshlanish vaqti hozirgi vaqtdan keyin bo'lishi kerak!" if lang == "uz" else "Время начала должно быть в будущем!")
            return
        
        if start_time > datetime.now() + timedelta(days=settings.MAX_CONTEST_DURATION_DAYS):
            await message.answer(f"Konkurs {settings.MAX_CONTEST_DURATION_DAYS} kundan ko'p davom eta olmaydi!" if lang == "uz" else f"Конкурс не может длиться более {settings.MAX_CONTEST_DURATION_DAYS} дней!")
            return
        
        await state.update_data(start_time=start_time)
        await message.answer(get_text("end_time", lang))
        await state.set_state(ContestCreation.waiting_for_end_time)
        
    except ValueError:
        await message.answer(get_text("invalid_format", lang))

@router.message(ContestCreation.waiting_for_end_time)
async def process_end_time(message: Message, state: FSMContext, db: AsyncSession, lang: str):
    try:
        contest_data = await state.get_data()
        start_time = contest_data["start_time"]
        
        try:
            end_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
            if end_time <= start_time:
                await message.answer("Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak!" if lang == "uz" else "Время окончания должно быть после времени начала!")
                return
            await state.update_data(end_time=end_time, max_participants=None)
        except ValueError:
            max_participants = int(message.text)
            if max_participants < 1 or max_participants > settings.MAX_PARTICIPANTS:
                raise ValueError
            await state.update_data(end_time=None, max_participants=max_participants)
        
        channel_service = ChannelService(db)
        channels = await channel_service.get_user_channels(message.from_user.id)
        
        if not channels:
            await message.answer("Sizda kanallar yo'q!" if lang == "uz" else "У вас нет каналов!")
            await state.clear()
            return
        
        await message.answer(
            get_text("select_channel", lang),
            reply_markup=kb.channel_selection(channels, lang)
        )
        await state.set_state(ContestCreation.waiting_for_channel_selection)
        
    except ValueError:
        await message.answer(get_text("invalid_format", lang))

@router.callback_query(F.data.startswith("select_channel:"), ContestCreation.waiting_for_channel_selection)
async def process_channel_selection(callback: CallbackQuery, state: FSMContext, db: AsyncSession, lang: str):
    channel_id = int(callback.data.split(":")[1])
    contest_data = await state.get_data()
    
    contest_service = ContestService(db)
    analytics_service = AnalyticsService(db)
    
    contest = await contest_service.create_contest(
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
    
    await analytics_service.track_user_action(
        callback.from_user.id,
        "contest_created",
        {"contest_id": contest.id}
    )
    
    metrics.record_contest("created")
    
    await callback.message.edit_text(
        get_text("contest_created", lang),
        reply_markup=kb.main_menu(lang)
    )
    await state.clear()

@router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    contest_id = int(callback.data.split(":")[1])
    
    participation_service = ParticipationService(db)
    contest_service = ContestService(db)
    analytics_service = AnalyticsService(db)
    
    contest = await contest_service.get_contest(contest_id)
    if not contest or contest.status != "active":
        await callback.answer(get_text("contest_ended", lang), show_alert=True)
        return
    
    is_participating = await participation_service.is_participating(contest_id, callback.from_user.id)
    if is_participating:
        await callback.answer(get_text("already_participating", lang), show_alert=True)
        return
    
    if contest.max_participants:
        current_participants = await participation_service.get_participants_count(contest_id)
        if current_participants >= contest.max_participants:
            await callback.answer("Konkurs to'ldi!" if lang == "uz" else "Конкурс заполнен!", show_alert=True)
            return
    
    from app.services.subscription_service import SubscriptionService
    subscription_service = SubscriptionService()
    
    force_sub_channels = await subscription_service.get_force_sub_channels()
    for channel in force_sub_channels:
        if not await subscription_service.check_subscription(callback.from_user.id, channel.channel_id):
            await callback.answer(get_text("not_subscribed", lang), show_alert=True)
            return
    
    await participation_service.add_participant(contest_id, callback.from_user.id)
    
    participants_count = await participation_service.get_participants_count(contest_id)
    new_keyboard = kb.contest_participation(
        contest_id, participants_count, contest.participate_button_text
    )
    
    await analytics_service.track_user_action(
        callback.from_user.id,
        "contest_joined",
        {"contest_id": contest_id}
    )
    
    await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    await callback.answer(get_text("participation_confirmed", lang), show_alert=True)

@router.callback_query(F.data.startswith("contest_stats:"))
async def contest_stats_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    contest_id = int(callback.data.split(":")[1])
    
    contest_service = ContestService(db)
    analytics_service = AnalyticsService(db)
    
    contest = await contest_service.get_contest(contest_id)
    if not contest:
        await callback.answer("Konkurs topilmadi!" if lang == "uz" else "Конкурс не найден!", show_alert=True)
        return
    
    stats = await analytics_service.get_contest_analytics(contest_id)
    participants_count = len(contest.participants) if contest.participants else 0
    
    text = f"📊 *{contest.title} statistikasi:*\n\n" if lang == "uz" else f"📊 *Статистика {contest.title}:*\n\n"
    text += f"👥 Qatnashchilar: {participants_count}\n"
    text += f"👀 Ko'rishlar: {contest.view_count}\n"
    text += f"📅 Yaratilgan: {contest.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    text += f"▶️ Boshlanish: {contest.start_time.strftime('%d.%m.%Y %H:%M')}\n"
    
    if contest.end_time:
        text += f"⏹ Tugash: {contest.end_time.strftime('%d.%m.%Y %H:%M')}\n"
    elif contest.max_participants:
        text += f"🎯 Maksimal: {contest.max_participants} kishi\n"
    
    text += f"🏆 G'oliblar: {contest.winners_count}\n"
    text += f"📈 Status: {contest.status.upper()}"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.contest_management(contest_id, contest.status, lang)
    )

@router.callback_query(F.data.startswith("start_contest:"))
async def start_contest_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    if callback.from_user.id not in settings.ADMIN_IDS:
        contest_id = int(callback.data.split(":")[1])
        contest_service = ContestService(db)
        contest = await contest_service.get_contest(contest_id)
        
        if not contest or contest.owner_id != callback.from_user.id:
            await callback.answer("Ruxsat yo'q!" if lang == "uz" else "Доступ запрещен!", show_alert=True)
            return
    
    contest_id = int(callback.data.split(":")[1])
    contest_service = ContestService(db)
    
    await contest_service.update_contest_status(contest_id, "active")
    await callback.answer("Konkurs boshlandi!" if lang == "uz" else "Конкурс запущен!", show_alert=True)
    
    contest = await contest_service.get_contest(contest_id)
    await callback.message.edit_reply_markup(
        reply_markup=kb.contest_management(contest_id, "active", lang)
    )

@router.callback_query(F.data.startswith("stop_contest:"))
async def stop_contest_callback(callback: CallbackQuery, db: AsyncSession, lang: str):
    contest_id = int(callback.data.split(":")[1])
    contest_service = ContestService(db)
    
    contest = await contest_service.get_contest(contest_id)
    if not contest or (contest.owner_id != callback.from_user.id and callback.from_user.id not in settings.ADMIN_IDS):
        await callback.answer("Ruxsat yo'q!" if lang == "uz" else "Доступ запрещен!", show_alert=True)
        return
    
    from app.services.winner_service import WinnerService
    winner_service = WinnerService(db)
    
    await contest_service.update_contest_status(contest_id, "ended")
    winners = await winner_service.select_winners(contest_id, contest.winners_count)
    
    if winners and contest.message_id:
        try:
            winners_text = get_text("winners_announced", lang) + "\n\n"
            for i, winner in enumerate(winners, 1):
                user_link = f"[{winner.first_name or 'User'}](tg://user?id={winner.id})"
                winners_text += get_text("winner_position", lang, position=i) + f" {user_link}\n"
            
            await callback.bot.send_message(
                chat_id=contest.channel_id,
                text=winners_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            pass
    
    await callback.answer("Konkurs to'xtatildi va g'oliblar e'lon qilindi!" if lang == "uz" else "Конкурс остановлен и победители объявлены!", show_alert=True)
    
    await callback.message.edit_reply_markup(
        reply_markup=kb.contest_management(contest_id, "ended", lang)
    )
