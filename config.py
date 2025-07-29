from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = "your_bot_token_here"
    WEBHOOK_URL: str = "https://your-domain.com"
    SECRET_KEY: str = "your-secret-key-here"
    
    class Config:
        env_file = ".env"

settings = Settings()
