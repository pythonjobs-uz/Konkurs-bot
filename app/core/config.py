from pydantic_settings import BaseSettings
from typing import Optional, List
import secrets

class Settings(BaseSettings):
    BOT_TOKEN: str
    BOT_USERNAME: str = "konkurs_bot"
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./konkurs_bot.db"
    REDIS_URL: str = "redis://localhost:6379"
    
    ADMIN_IDS: List[int] = []
    SUPER_ADMIN_ID: Optional[int] = None
    
    SPONSOR_CHANNEL_ID: Optional[int] = None
    SPONSOR_CHANNEL_USERNAME: Optional[str] = None
    
    WELCOME_IMAGE_URL: str = "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/image-DqoVaYibRQZcQAktSp0nc65x4QKQLs.png"
    SPONSOR_IMAGE_URL: str = "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/image-DD29J2aQr5RSmcKRitFxTbpXr9sLvg.png"
    
    USE_WEBHOOK: bool = False
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: str = secrets.token_urlsafe(32)
    
    DEBUG: bool = False
    
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW: int = 60
    
    MAX_CONTEST_DURATION_DAYS: int = 30
    MAX_WINNERS_COUNT: int = 100
    MAX_PARTICIPANTS: int = 10000
    
    ANALYTICS_RETENTION_DAYS: int = 90
    
    ENCRYPTION_KEY: str = secrets.token_urlsafe(32)
    
    class Config:
        env_file = ".env"

settings = Settings()
