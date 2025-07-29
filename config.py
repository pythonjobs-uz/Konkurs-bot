from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite:///./contest_bot.db"
    WEBHOOK_URL: str
    SECRET_KEY: str = "your-secret-key-here"
    
    class Config:
        env_file = ".env"

settings = Settings()
