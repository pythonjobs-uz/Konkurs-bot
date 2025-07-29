from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import asyncio

from aiogram import Bot
from app.core.database import db
from app.services.contest_service import ContestService
from app.services.winner_service import WinnerService
from app.services.analytics_service import AnalyticsService
from app.services.channel_service import ChannelService
from app.services.broadcast_service import BroadcastService
from app.keyboards.inline import contest_participation_keyboard
from app.core.database import Channel, UserAnalytics
from sqlalchemy import delete

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
    
    async def start(self):
        self.running = True
        logger.info("Scheduler service started")
        
        # Start all scheduler tasks
        await asyncio.gather(
            self.check_contests(),
            self.cleanup_expired_cache(),
            self.update_channel_stats(),
            self.check_premium_expiry()
        )
    
    async def stop(self):
        self.running = False
        logger.info("Scheduler service stopped")
    
    async def check_contests(self):
        while self.running:
            try:
                contests = await db.get_active_contests()
                
                for contest in contests:
                    now = datetime.now()
                    
                    # Start pending contests
                    if contest['status'] == 'pending' and contest['start_time']:
                        start_time = datetime.fromisoformat(contest['start_time'].replace('Z', '+00:00'))
                        if start_time <= now:
                            await self.start_contest(contest)
                    
                    # End active contests
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
                            await self.end_contest(contest)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in contest scheduler: {e}")
                await asyncio.sleep(60)
    
    async def start_contest(self, contest):
        try:
            # Create contest message
            text = f"🎉 <b>{contest['title']}</b>\n\n{contest['description']}"
            
            if contest['prize_description']:
                text += f"\n\n🎁 <b>Sovg'alar:</b>\n{contest['prize_description']}"
            
            if contest['requirements']:
                text += f"\n\n📋 <b>Shartlar:</b>\n{contest['requirements']}"
            
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
                message = await self.bot.send_photo(
                    chat_id=contest['channel_id'],
                    photo=contest['image_file_id'],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                message = await self.bot.send_message(
                    chat_id=contest['channel_id'],
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            await db.update_contest_status(contest['id'], 'active')
            await db.set_contest_message_id(contest['id'], message.message_id)
            
            # Send notification to contest owner
            await self.bot.send_message(
                chat_id=contest['owner_id'],
                text=f"🎉 Sizning '{contest['title']}' konkursingiz boshlandi!\n\n📊 Natijalarni kuzatib boring.",
                parse_mode="HTML"
            )
            
            logger.info(f"Started contest {contest['id']}")
            
        except Exception as e:
            logger.error(f"Failed to start contest {contest['id']}: {e}")
    
    async def end_contest(self, contest):
        try:
            success = await ContestService.end_contest(contest['id'])
            
            if success:
                winners = await db.get_contest_winners(contest['id'])
                
                # Announce winners in channel
                if winners:
                    winners_text = f"🏆 <b>{contest['title']} - G'oliblar e'lon qilindi!</b>\n\n"
                    
                    for winner in winners:
                        position_emoji = "🥇" if winner['position'] == 1 else "🥈" if winner['position'] == 2 else "🥉" if winner['position'] == 3 else "🏅"
                        winners_text += f"{position_emoji} <b>{winner['position']}-o'rin:</b> <a href='tg://user?id={winner['id']}'>{winner.get('first_name', 'User')}</a>\n"
                    
                    winners_text += f"\n🎉 Tabriklaymiz! Adminlar siz bilan bog'lanadi."
                    
                    await self.bot.send_message(
                        chat_id=contest['channel_id'],
                        text=winners_text,
                        parse_mode="HTML"
                    )
                
                # Notify contest owner
                await self.bot.send_message(
                    chat_id=contest['owner_id'],
                    text=f"🏁 '{contest['title']}' konkursi tugadi!\n\n🏆 G'oliblar: {len(winners)} kishi\n👥 Jami qatnashchilar: {contest['participant_count']}",
                    parse_mode="HTML"
                )
                
                # Send notifications to winners
                await BroadcastService.send_contest_notification(self.bot, contest['id'], "ended")
                
                logger.info(f"Ended contest {contest['id']} with {len(winners)} winners")
            
        except Exception as e:
            logger.error(f"Failed to end contest {contest['id']}: {e}")
    
    async def cleanup_expired_cache(self):
        while self.running:
            try:
                # This would be implemented based on Redis capabilities
                # For now, we'll just log that cleanup is running
                logger.debug("Running cache cleanup")
                await asyncio.sleep(3600)  # Run every hour
                
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(3600)
    
    async def update_channel_stats(self):
        while self.running:
            try:
                channels = await db.connection.execute("SELECT * FROM channels WHERE is_active = 1")
                channels = await channels.fetchall()
                
                for channel in channels:
                    try:
                        member_count = await self.bot.get_chat_member_count(channel[1])  # channel_id
                        await db.connection.execute("""
                            UPDATE channels SET member_count = ? WHERE id = ?
                        """, (member_count, channel[0]))  # id
                    except Exception:
                        continue
                
                await db.connection.commit()
                logger.debug("Updated channel statistics")
                await asyncio.sleep(3600)  # Run every hour
                
            except Exception as e:
                logger.error(f"Error updating channel stats: {e}")
                await asyncio.sleep(3600)
    
    async def check_premium_expiry(self):
        while self.running:
            try:
                cursor = await db.connection.execute("""
                    SELECT id FROM users 
                    WHERE is_premium = 1 AND premium_until < datetime('now')
                """)
                expired_users = await cursor.fetchall()
                
                for user in expired_users:
                    await db.connection.execute("""
                        UPDATE users SET is_premium = 0, premium_until = NULL WHERE id = ?
                    """, (user[0],))
                    
                    # Notify user about premium expiry
                    try:
                        await self.bot.send_message(
                            chat_id=user[0],
                            text="⚠️ Sizning Premium obunangiz tugadi!\n\nYangilash uchun /premium buyrug'ini bosing.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                
                await db.connection.commit()
                
                if expired_users:
                    logger.info(f"Expired premium for {len(expired_users)} users")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error checking premium expiry: {e}")
                await asyncio.sleep(3600)

scheduler_service = SchedulerService(None)

# scheduler.add_job(
#     scheduler_service.check_contests,
#     CronTrigger(second=0),
#     id="check_contests",
#     max_instances=1
# )

# scheduler.add_job(
#     scheduler_service.cleanup_old_data,
#     CronTrigger(hour=2, minute=0),
#     id="cleanup_old_data",
#     max_instances=1
# )

# scheduler.add_job(
#     scheduler_service.update_channel_stats,
#     CronTrigger(hour=6, minute=0),
#     id="update_channel_stats",
#     max_instances=1
# )
