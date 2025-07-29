from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    BOT_TOKEN: str = "6123456789:AAEhBOweik6ad2xkTVKlfPn7LMRjMOxdlUI"
    BOT_USERNAME: str = "konkurs_bot"
    
    DATABASE_PATH: str = "contest_bot.db"
    
    ADMIN_IDS: List[int] = [123456789]
    SUPER_ADMIN_ID: Optional[int] = 123456789
    
    SPONSOR_CHANNEL_ID: Optional[int] = -1001234567890
    SPONSOR_CHANNEL_USERNAME: Optional[str] = "sponsor_channel"
    
    USE_WEBHOOK: bool = False
    WEBHOOK_URL: Optional[str] = "https://your-domain.com"
    WEBHOOK_SECRET: str = "your_webhook_secret_here"
    
    SECRET_KEY: str = "your-super-secret-key-here"
    DEBUG: bool = True
    
    REDIS_URL: str = "redis://localhost:6379"
    
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW: int = 60
    
    MAX_CONTEST_DURATION_DAYS: int = 30
    MAX_WINNERS_COUNT: int = 100
    MAX_PARTICIPANTS: int = 10000
    
    PREMIUM_PRICE: int = 50000
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
