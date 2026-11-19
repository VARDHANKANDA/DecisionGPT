"""Application configuration, loaded from environment variables.

Kept as a single Pydantic settings object so every service reads
configuration the same way instead of calling os.environ ad hoc.
"""
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

# Local env files are located from this file, not from the process working directory: the backend is started from the repo
# root (.claude/launch.json, README), from backend/ (Dockerfile, alembic) and by scripts, and a bare ".env" meant a different
# file - or none - in each. Later files win, so backend/.env overrides the repo-root .env. Real process environment
# variables (docker/CI/hosting) always win over both. Both files are git-ignored and docker-ignored.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Default precedence (init > process env > .env files) with one change: an empty ``KEY=`` line in an env file counts as
        "not set", so a blank placeholder in one file cannot erase a value set in the other. A blank *process* environment
        variable still wins (that is how a run is told to disable the AI path)."""
        files = DotEnvSettingsSource(
            settings_cls,
            env_file=getattr(dotenv_settings, "env_file", ENV_FILES),
            env_file_encoding=getattr(dotenv_settings, "env_file_encoding", None),
            env_ignore_empty=True,
        )
        return init_settings, env_settings, files, file_secret_settings

    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(default="change-me-in-production", repr=False)

    # Database
    database_url: str = Field(default="postgresql+psycopg://decisiongpt:decisiongpt@localhost:5432/decisiongpt", repr=False)  # holds credentials

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("postgres://"):
                return "postgresql+psycopg://" + s[len("postgres://"):]
            if s.startswith("postgresql://") and not s.startswith("postgresql+"):
                return "postgresql+psycopg://" + s[len("postgresql://"):]
            return s
        return v

    # Frontend / CORS
    frontend_origin: str = "http://localhost:3000"

    # OpenAI (the only AI provider; official SDK, Responses API). Leave OPENAI_API_KEY unset or blank to run in deterministic
    # rule-based mode (no network). Server-side only: never exposed to the browser. OPENAI_MODEL is configurable; a blank value
    # uses the default below. The model must be available to your account and support structured outputs.
    openai_api_key: Optional[str] = Field(default=None, repr=False)  # repr=False: never shown in a settings repr/traceback
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 20
    openai_max_retries: int = 1  # extra attempts for errors that cannot have been processed (429 without exhausted quota, connection failure)
    # Kill switches. With analytics_llm_enabled off the legacy deterministic router answers; with the explainer off the answer is the
    # deterministic verified-facts text only.
    analytics_llm_enabled: bool = True
    # Upload resource limits (per file). A file over either limit is rejected with a clear message and nothing is stored.
    max_upload_bytes: int = 25 * 1024 * 1024
    max_upload_rows: int = 200_000
    # Business uploads: the ORIGINAL file is kept unchanged (so nothing the person uploaded is ever lost) under this folder, in a path built only from
    # validated ids. A file that failed to import is removed. A file whose rows could not be imported more than this share of the time is refused as a
    # whole (most rows unreadable usually means a wrong column mapping or date format, not bad rows).
    business_upload_path: str = "./data/business_uploads"
    max_skipped_row_share: float = 0.5
    analytics_explain_enabled: bool = True  # ANALYTICS_EXPLAIN_ENABLED=false: no restatement request is ever sent (classification is unaffected)

    @field_validator("analytics_llm_enabled", "analytics_explain_enabled", mode="before")
    @classmethod
    def _blank_switch_is_the_default(cls, v):
        """``ANALYTICS_EXPLAIN_ENABLED=`` (blank) in the process environment means "not set", like a blank line in an env file, instead
        of a startup crash. Any real value (false/0/no/off, true/1/yes/on) is parsed by pydantic as usual."""
        return True if isinstance(v, str) and not v.strip() else v

    # Research console
    research_console_enabled: bool = True
    research_console_token: str = Field(default="change-me-research-console-token", repr=False)

    # Model registry
    model_registry_path: str = "./models"

    # Research platform: where uploaded research datasets are stored
    research_data_path: str = "./data/research_uploads"

    # Cloud Object Storage (S3 / Cloudflare R2 / MinIO) for zero-data-loss cloud hosting
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_endpoint_url: Optional[str] = None
    s3_access_key_id: Optional[str] = Field(default=None, repr=False)
    s3_secret_access_key: Optional[str] = Field(default=None, repr=False)

    # Auth (Phase 4). When auth_enabled is False the API runs open (local
    # dev / tests); when True every SME + research route requires a bearer
    # token issued by /api/v1/auth/login.
    auth_enabled: bool = False
    jwt_secret: str = Field(default="change-me-jwt-secret", repr=False)
    jwt_ttl_seconds: int = 60 * 60 * 12
    # Token claims (RFC 7519 / RFC 8725): a token is accepted only for this issuer and audience. JWT_SECRET_PREVIOUS lets tokens signed
    # with the prior secret verify (never sign) while a rotation drains; remove it after one TTL.
    jwt_issuer: str = "decisiongpt"
    jwt_audience: str = "decisiongpt-api"
    jwt_leeway_seconds: int = 30
    jwt_secret_previous: Optional[str] = Field(default=None, repr=False)

    # Authentication abuse protection (app/services/rate_limit_service.py). Counters live in the application database so every worker and
    # replica shares them. Fixed windows; limits count FAILED sign-ins (and every sign-up / password-change attempt). Nothing locks an account:
    # a limit only delays further attempts until the window ends. Hardened environments refuse to start with the limiter off.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 15 * 60
    rate_limit_login_per_ip: int = 20          # failed sign-ins from one client address, across all accounts
    rate_limit_login_per_account_ip: int = 5   # failed sign-ins for one account from one client address
    rate_limit_login_per_account: int = 40     # failed sign-ins for one account from anywhere (distributed guessing brake)
    rate_limit_register_per_ip: int = 10       # sign-up attempts per client address per window of rate_limit_register_window_seconds
    rate_limit_register_window_seconds: int = 60 * 60
    rate_limit_password_change_per_user: int = 5   # failed current-password checks per signed-in user
    # Comma-separated IPs / CIDRs of reverse proxies whose X-Forwarded-For header may be believed. Empty (the default) = trust no header: the
    # client address is the TCP peer. Set it when, and only when, the API sits behind a proxy you operate.
    trusted_proxies: str = ""
    # Interactive API documentation (/docs, /redoc, /openapi.json). Blank = on in development and test, off in staging and production.
    docs_enabled: Optional[bool] = None

    @property
    def llm_enabled(self) -> bool:
        """True when an OpenAI API key is configured (the name is kept for the many callers that ask 'is AI available?')."""
        return bool(self.openai_api_key)

    @property
    def analytics_llm_active(self) -> bool:
        return bool(self.analytics_llm_enabled and self.llm_enabled)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def hardened(self) -> bool:
        """staging and production: authentication, real secrets and a migrated PostgreSQL are required (see security_config)."""
        return self.environment.strip().lower() in ("staging", "production")

    @property
    def docs_active(self) -> bool:
        return self.docs_enabled if self.docs_enabled is not None else not self.hardened


@lru_cache
def get_settings() -> Settings:
    return Settings()
