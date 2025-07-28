from aiogram import Dispatcher

from app.handlers.start import router as start_router
from app.handlers.menu import router as menu_router
from app.handlers.contest import router as contest_router
from app.handlers.admin import router as admin_router
from app.handlers.premium import router as premium_router
from app.handlers.analytics import router as analytics_router

def register_handlers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(contest_router)
    dp.include_router(admin_router)
    dp.include_router(premium_router)
    dp.include_router(analytics_router)
