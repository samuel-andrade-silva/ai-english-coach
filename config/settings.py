from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    dry_run: bool = True

    # Telegram
    telegram_bot_token: str = ""

    # LLMs e APIs
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "openai/gpt-oss-120b"

    # Decisão tipada (Jev)
    typesafe_api_key: str = ""
    typesafe_model: str = "typesafe:jev-latest"

    confianca_minima_router: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()