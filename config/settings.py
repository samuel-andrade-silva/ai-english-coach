from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = ""

    # Qdrant Vector DB
    # (NUNCA coloque URL/endpoint real como default no código!)
    vector_db_type: str = "qdrant"
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # Decisão tipada (Jev)
    confianca_minima_router: float = 0.6

    # FASE 7: Busca Web (Tavily) & Observabilidade (LangSmith)
    tavily_api_key: Optional[str] = None

    langsmith_tracing: bool = False
    langsmith_api_key: Optional[str] = None

    # AnkiConnect (padrão local; aponte para o IP/hostname do Anki
    # quando ele rodar em outra máquina da rede)
    anki_connect_url: str = "http://localhost:8765"

    # Configuração do Pydantic
    # Lê o arquivo .env e ignora variáveis extras não declaradas
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
