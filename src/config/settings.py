from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    META_API_TOKEN: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    USE_MOCK_DATA: bool = True

    # Extra='ignore' prevents crashes if the user puts unrelated variables in .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

