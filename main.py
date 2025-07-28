import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import uvicorn

from app.core.config import settings
from app.core.database import init_db
from app.core.redis import init_redis
from app.handlers import register_handlers
from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.i18n import I18nMiddleware
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.analytics import AnalyticsMiddleware
from app.services.scheduler import scheduler
from app.api.routes import admin_router, webhook_router, analytics_router
from app.core.metrics import setup_metrics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Konkurs Bot...")
    
    await init_db()
    await init_redis()
    
    dp.middleware(ThrottlingMiddleware())
    dp.middleware(AnalyticsMiddleware())
    dp.middleware(I18nMiddleware())
    dp.middleware(DatabaseMiddleware())
    
    register_handlers(dp)
    setup_metrics(app)
    
    scheduler.start()
    
    if settings.USE_WEBHOOK:
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}/webhook",
            secret_token=settings.WEBHOOK_SECRET
        )
        logger.info(f"🔗 Webhook set to {settings.WEBHOOK_URL}/webhook")
    else:
        asyncio.create_task(dp.start_polling(bot))
        logger.info("📡 Polling started")
    
    logger.info("✅ Bot started successfully!")
    
    yield
    
    logger.info("🛑 Shutting down bot...")
    scheduler.shutdown()
    await bot.session.close()

app = FastAPI(
    title="Konkurs Bot API",
    description="Advanced Telegram Contest Bot with Analytics",
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
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])

@app.get("/")
async def root():
    return {
        "message": "🎉 Konkurs Bot API v2.0",
        "status": "operational",
        "features": ["contests", "analytics", "webhooks", "admin_panel"]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "bot_info": await bot.get_me(),
        "database": "connected",
        "redis": "connected",
        "scheduler": "running"
    }

if settings.USE_WEBHOOK:
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.WEBHOOK_SECRET
    )
    webhook_requests_handler.register(app, path="/webhook")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4
    )
