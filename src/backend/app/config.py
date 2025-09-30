"""Application configuration (Pydantic v2)"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Database settings
    database_url: Optional[str] = None  # prefer DATABASE_URL if provided
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "llm_streaming"

    # LLM Provider settings
    openai_api_key: str = ""
    llm_model: str = "gpt-3.5-turbo"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000

    # Application settings
    app_name: str = "LLM Streaming Service"
    debug: bool = False

    # API authentication (optional)
    api_key: str = ""  # if set, requests must include header X-API-Key

    # Rate limiting (simple in-memory)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Logging
    log_json: bool = True

    # Pagination defaults
    default_page_limit: int = 10
    max_page_limit: int = 100

    def model_post_init(self, __context: dict) -> None:
        # Build database_url from parts if not provided
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

