import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis, redis_manager
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.i18n import I18nMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.analytics import AnalyticsMiddleware
from app.handlers import start, menu, contest, admin
from app.api.routes import router as api_router
from app.services.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Konkurs Bot...")
    
    try:
        await init_redis()
        await init_db()
        
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        storage = RedisStorage(redis_manager.redis) if redis_manager.redis else MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        dp.middleware(DatabaseMiddleware())
        dp.middleware(I18nMiddleware())
        dp.middleware(ThrottlingMiddleware())
        dp.middleware(AnalyticsMiddleware())
        
        dp.include_router(start.router)
        dp.include_router(menu.router)
        dp.include_router(contest.router)
        dp.include_router(admin.router)
        
        app.state.bot = bot
        app.state.dp = dp
        
        if settings.USE_WEBHOOK and settings.WEBHOOK_URL:
            await bot.set_webhook(
                url=f"{settings.WEBHOOK_URL}/webhook",
                secret_token=settings.WEBHOOK_SECRET
            )
            logger.info(f"Webhook set to {settings.WEBHOOK_URL}/webhook")
        else:
            asyncio.create_task(start_polling(dp, bot))
            logger.info("Started polling mode")
        
        scheduler.start()
        logger.info("Scheduler started")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down...")
        
        if hasattr(app.state, 'bot'):
            await app.state.bot.session.close()
        
        scheduler.shutdown()
        await close_redis()
        await close_db()
        
        logger.info("Shutdown complete")

async def start_polling(dp: Dispatcher, bot: Bot):
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Polling error: {e}")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Konkurs Bot API",
        description="Telegram Contest Bot API",
        version="2.0.0",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router, prefix="/api/v1")
    
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
