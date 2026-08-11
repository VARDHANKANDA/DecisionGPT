"""Application configuration, loaded from environment variables.

Kept as a single Pydantic settings object so every service reads
configuration the same way instead of calling os.environ ad hoc.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+psycopg://decisiongpt:decisiongpt@localhost:5432/decisiongpt"

    # Frontend / CORS
    frontend_origin: str = "http://localhost:3000"

    # LLM provider (abstracted — see app/services/llm_service.py)
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None

    # Research console
    research_console_enabled: bool = True
    research_console_token: str = "change-me-research-console-token"

    # Model registry
    model_registry_path: str = "./models"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_provider and self.llm_api_key)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
