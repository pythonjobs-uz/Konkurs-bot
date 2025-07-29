import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from config import settings
from app.core.database import db
from app.core.redis import cache
from app.handlers import start, contest, menu, admin
from app.middlewares.analytics import AnalyticsMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.services.scheduler import SchedulerService

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot_instance = None
scheduler_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance, scheduler_service
    
    # Initialize database
    await db.init_db()
    logger.info("Database initialized")
    
    # Initialize Redis
    await cache.init_redis()
    logger.info("Redis initialized")
    
    # Initialize bot
    bot_instance = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Add middlewares
    dp.message.middleware(AnalyticsMiddleware())
    dp.callback_query.middleware(AnalyticsMiddleware())
    dp.message.middleware(ThrottlingMiddleware(settings.RATE_LIMIT_MESSAGES, settings.RATE_LIMIT_WINDOW))
    dp.callback_query.middleware(ThrottlingMiddleware(settings.RATE_LIMIT_MESSAGES, settings.RATE_LIMIT_WINDOW))
    
    # Include routers
    dp.include_router(start.router)
    dp.include_router(contest.router)
    dp.include_router(menu.router)
    dp.include_router(admin.router)
    
    # Start scheduler
    scheduler_service = SchedulerService(bot_instance)
    asyncio.create_task(scheduler_service.start())
    logger.info("Scheduler service started")
    
    if settings.USE_WEBHOOK:
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot_instance,
            secret_token=settings.WEBHOOK_SECRET
        )
        webhook_requests_handler.register(app, path="/webhook")
        
        await bot_instance.set_webhook(
            url=f"{settings.WEBHOOK_URL}/webhook",
            secret_token=settings.WEBHOOK_SECRET
        )
        logger.info("Webhook mode enabled")
    else:
        asyncio.create_task(dp.start_polling(bot_instance))
        logger.info("Polling mode enabled")
    
    app.state.bot = bot_instance
    app.state.dp = dp
    
    yield
    
    # Cleanup
    if scheduler_service:
        await scheduler_service.stop()
    
    if settings.USE_WEBHOOK:
        await bot_instance.delete_webhook()
    
    await bot_instance.session.close()
    await cache.close()
    await db.close()
    logger.info("Application shutdown complete")

app = FastAPI(
    title="Konkurs Bot v3.0",
    description="Advanced Telegram Contest Bot with Premium Features",
    version="3.0.0",
    lifespan=lifespan
)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def read_root(request: Request):
    stats = await db.get_statistics()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "stats": stats
    })

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "3.0.0"}

@app.get("/stats")
async def get_stats():
    stats = await db.get_statistics()
    return {"status": "success", "data": stats}

@app.get("/terms")
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/privacy")
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
