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

    # LLM provider (abstracted — see app/services/llm_service.py).
    # Leave llm_api_key unset to run in deterministic template mode.
    llm_provider: Optional[str] = None  # openai | openai_compatible | anthropic
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None  # defaults per provider
    llm_timeout_seconds: int = 30

    # Research console
    research_console_enabled: bool = True
    research_console_token: str = "change-me-research-console-token"

    # Model registry
    model_registry_path: str = "./models"

    # Research platform: where uploaded research datasets are stored
    research_data_path: str = "./data/research_uploads"

    # Auth (Phase 4). When auth_enabled is False the API runs open (local
    # dev / tests); when True every SME + research route requires a bearer
    # token issued by /api/v1/auth/login.
    auth_enabled: bool = False
    jwt_secret: str = "change-me-jwt-secret"
    jwt_ttl_seconds: int = 60 * 60 * 12

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_provider and self.llm_api_key)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
