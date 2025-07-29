from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    BOT_TOKEN: str
    BOT_USERNAME: str = "konkurs_bot"
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./konkurs_bot.db"
    REDIS_URL: str = "redis://localhost:6379"
    
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    SUPER_ADMIN_ID: Optional[int] = None
    ADMIN_IDS: List[int] = []
    
    SPONSOR_CHANNEL_ID: Optional[int] = None
    SPONSOR_CHANNEL_USERNAME: Optional[str] = None
    
    USE_WEBHOOK: bool = False
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: str = secrets.token_urlsafe(32)
    
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ENCRYPTION_KEY: str = secrets.token_urlsafe(32)
    
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW: int = 60
    
    MAX_CONTEST_DURATION_DAYS: int = 30
    MAX_WINNERS_COUNT: int = 100
    MAX_PARTICIPANTS: int = 10000
    
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    REDIS_POOL_SIZE: int = 10
    
    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")
    
    @property
    def is_postgresql(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

if settings.SUPER_ADMIN_ID and settings.SUPER_ADMIN_ID not in settings.ADMIN_IDS:
    settings.ADMIN_IDS.append(settings.SUPER_ADMIN_ID)
