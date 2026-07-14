"""
Centralized application settings.

Single source of truth for every environment-driven knob in SwarmWarm. Reads from
the process environment and the local .env file (via pydantic-settings). Other modules
should import `settings` from here rather than calling os.getenv directly.
"""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the repository root (…/SwarmWarm).
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_SQLITE_PATH = os.path.join(ROOT_DIR, "swarmwarm.db")
# SQLAlchemy sqlite URLs use forward slashes even on Windows.
_DEFAULT_DATABASE_URL = "sqlite:///" + _DEFAULT_SQLITE_PATH.replace("\\", "/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(ROOT_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- Runtime -----
    ENV: str = "development"
    PORT: int = 8000

    # ----- Database -----
    # Default: local SQLite file. In production set e.g.
    #   DATABASE_URL=postgresql+psycopg://user:pass@host:5432/swarmwarm
    DATABASE_URL: str = _DEFAULT_DATABASE_URL

    # ----- Crypto / auth secrets -----
    SWARMWARM_SECRET_KEY: Optional[str] = None
    SWARMWARM_JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ----- Access control -----
    # Comma-separated list of emails that are granted the admin role on signup.
    ADMIN_EMAILS: List[str] = ["ieee.dobby1998@gmail.com"]

    # Login throttling (per email+IP) to blunt brute-force attempts.
    LOGIN_MAX_ATTEMPTS: int = 8
    LOGIN_WINDOW_SECONDS: int = 300

    # ----- CORS -----
    CORS_ORIGINS: List[str] = ["*"]

    # ----- Infra -----
    REDIS_BROKER_URL: str = "redis://localhost:6379/0"

    # ----- Local AI tunnel -----
    LOCAL_AI_TUNNEL_URL: str = "http://localhost:11434"
    LOCAL_AI_API_KEY: str = ""
    LOCAL_AI_MODEL: str = "gemma"

    # ----- Feature flags -----
    # When true, onboarding performs a real SMTP/IMAP login before saving a mailbox.
    VALIDATE_MAILBOX_CONNECTIONS: bool = False

    # ----- Transactional email -----
    # console = print to stdout (dev). smtp = send via the SMTP_* settings below.
    EMAIL_BACKEND: str = "console"
    EMAIL_FROM: str = "no-reply@swarmwarm.io"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ----- Billing (Stripe) -----
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_SCALE: str = ""

    # ----- Observability -----
    SENTRY_DSN: str = ""

    @field_validator("ADMIN_EMAILS", "CORS_ORIGINS", mode="before")
    @classmethod
    def _split_csv(cls, v):
        """Allow comma-separated strings in .env for list-typed settings."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV.lower().startswith("prod")

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
