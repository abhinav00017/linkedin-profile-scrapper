"""Configuration. Every secret comes from the environment, never the repo."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Encrypts stored LinkedIn cookies. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str

    db_path: str = "data/keys.db"

    # A key that works the moment the app boots, so the demo key survives a
    # wiped volume. Leave unset and no bootstrap key exists.
    bootstrap_api_key: str | None = None
    bootstrap_li_at: str | None = None
    bootstrap_jsessionid: str | None = None
    bootstrap_cookie_header: str | None = None

    # Caps exist to protect the LinkedIn account behind a key, not to
    # restrict the caller. Ordinary use never reaches them.
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 300

    request_timeout_seconds: float = 30.0
    version: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
