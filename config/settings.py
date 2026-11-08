from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações tipadas da aplicação lidas do arquivo .env."""

    dry_run: bool = True

    # LLMs e APIs
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Decisão tipada (Jev)
    typesafe_api_key: str = ""
    typesafe_model: str = "typesafe:jev-latest"

    confianca_minima_router: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()