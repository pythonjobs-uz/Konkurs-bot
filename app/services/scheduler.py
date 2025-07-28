from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import asyncio

from app.services.contest_service import ContestService
from app.services.winner_service import WinnerService
from app.services.analytics_service import AnalyticsService
from app.services.channel_service import ChannelService
from app.keyboards.inline import kb
from app.core.database import get_db, Channel
from app.core.redis import cache

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

class SchedulerService:
    def __init__(self):
        self.bot = None
    
    def set_bot(self, bot):
        self.bot = bot

    async def check_contests(self):
        try:
            async with get_db() as db:
                contest_service = ContestService(db)
                winner_service = WinnerService(db)
                analytics_service = AnalyticsService(db)
                
                contests = await contest_service.get_active_contests()
                
                for contest in contests:
                    now = datetime.utcnow()
                    
                    if contest.status == "pending" and contest.start_time <= now:
                        await self.start_contest(contest, analytics_service)
                    
                    elif contest.status == "active":
                        should_end = False
                        
                        if contest.end_time and contest.end_time <= now:
                            should_end = True
                        elif contest.max_participants and contest.participant_count >= contest.max_participants:
                            should_end = True
                        
                        if should_end:
                            await self.end_contest(contest, winner_service, analytics_service)
                            
        except Exception as e:
            logger.error(f"Error in check_contests: {e}")

    async def start_contest(self, contest, analytics_service):
        if not self.bot:
            logger.error("Bot not available for starting contest")
            return
        
        try:
            text = f"🎉 <b>{contest.title}</b>\n\n{contest.description}"
            
            if contest.prize_description:
                text += f"\n\n🎁 <b>Sovg'a:</b> {contest.prize_description}"
            
            text += f"\n\n⏰ Tugash: {contest.end_time.strftime('%d.%m.%Y %H:%M') if contest.end_time else 'Qatnashchilar soniga qarab'}"
            text += f"\n🏆 G'oliblar: {contest.winners_count} kishi"
            
            keyboard = kb.contest_participation(contest.id, 0, contest.participate_button_text)
            
            if contest.image_file_id:
                message = await self.bot.send_photo(
                    chat_id=contest.channel_id,
                    photo=contest.image_file_id,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                message = await self.bot.send_message(
                    chat_id=contest.channel_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            async with get_db() as db:
                contest_service = ContestService(db)
                await contest_service.update_contest_status(contest.id, "active")
                await contest_service.set_contest_message_id(contest.id, message.message_id)
            
            await analytics_service.track_contest_metric(contest.id, "started", 1)
            
            logger.info(f"Started contest {contest.id}")
            
        except Exception as e:
            logger.error(f"Failed to start contest {contest.id}: {e}")

    async def end_contest(self, contest, winner_service, analytics_service):
        if not self.bot:
            logger.error("Bot not available for ending contest")
            return
        
        try:
            winners = await winner_service.select_winners(contest.id, contest.winners_count)
            
            if winners:
                winners_text = "🏆 <b>G'oliblar e'lon qilindi:</b>\n\n"
                
                for i, winner in enumerate(winners, 1):
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
                    winners_text += f"{emoji} <b>{i}-o'rin:</b> <a href='tg://user?id={winner.id}'>{winner.first_name or 'User'}</a>\n"
                
                winners_text += f"\n🎉 Tabriklaymiz! Adminlar siz bilan bog'lanadi."
                
                await self.bot.send_message(
                    chat_id=contest.channel_id,
                    text=winners_text,
                    parse_mode="HTML"
                )
                
                for winner in winners:
                    try:
                        await self.bot.send_message(
                            chat_id=winner.id,
                            text=f"🎉 <b>Tabriklaymiz!</b>\n\nSiz <b>{contest.title}</b> konkursida g'olib bo'ldingiz!\n\nTez orada admin siz bilan bog'lanadi.",
                            parse_mode="HTML"
                        )
                    except:
                        pass
            
            async with get_db() as db:
                contest_service = ContestService(db)
                await contest_service.update_contest_status(contest.id, "ended")
            
            await analytics_service.track_contest_metric(contest.id, "ended", 1)
            await analytics_service.track_contest_metric(contest.id, "winners_count", len(winners))
            
            logger.info(f"Ended contest {contest.id} with {len(winners)} winners")
            
        except Exception as e:
            logger.error(f"Failed to end contest {contest.id}: {e}")

    async def cleanup_old_data(self):
        try:
            async with get_db() as db:
                from app.core.database import UserAnalytics
                from sqlalchemy import delete
                
                cutoff_date = datetime.utcnow() - timedelta(days=90)
                
                await db.execute(
                    delete(UserAnalytics).where(UserAnalytics.timestamp < cutoff_date)
                )
                
                await db.commit()
                logger.info("Cleaned up old analytics data")
                
        except Exception as e:
            logger.error(f"Error in cleanup_old_data: {e}")

    async def update_channel_stats(self):
        if not self.bot:
            return
        
        try:
            async with get_db() as db:
                channel_service = ChannelService(db)
                channels = await channel_service.get_all_active_channels()
                
                for channel in channels:
                    try:
                        member_count = await self.bot.get_chat_member_count(channel.channel_id)
                        await channel_service.update_member_count(channel.channel_id, member_count)
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Failed to update channel {channel.channel_id}: {e}")
                        continue
                        
                logger.info("Updated channel statistics")
                
        except Exception as e:
            logger.error(f"Error in update_channel_stats: {e}")

scheduler_service = SchedulerService()

scheduler.add_job(
    scheduler_service.check_contests,
    CronTrigger(second=0),
    id="check_contests",
    max_instances=1
)

scheduler.add_job(
    scheduler_service.cleanup_old_data,
    CronTrigger(hour=2, minute=0),
    id="cleanup_old_data",
    max_instances=1
)

scheduler.add_job(
    scheduler_service.update_channel_stats,
    CronTrigger(hour=6, minute=0),
    id="update_channel_stats",
    max_instances=1
)
