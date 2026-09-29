"""Central application settings using Pydantic BaseSettings."""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Enterprise Voice & Text Agent"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Audio Settings
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    AUDIO_FRAME_DURATION_MS: int = 20
    
    # Model APIs
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_LIVE_MODEL: str = "gemini-2.0-flash-exp"
    OPENAI_API_KEY: Optional[str] = None
    DEEPGRAM_API_KEY: Optional[str] = None
    
    # Database URIs
    SQLITE_DB_PATH: str = "data/storage/conversations.db"
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
