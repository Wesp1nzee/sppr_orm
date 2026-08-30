"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "СППР ОРМ"
    app_version: str = "0.1.0"
    app_env: str = "development"  # development | testing | production
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "insecure-dev-key-change-me"  # noqa: S105 — dev-дефолт, в проде задаётся через SECRET_KEY
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    csrf_exempt_paths: list[str] = ["/docs", "/redoc", "/openapi.json"]

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    database_url: str = "postgresql+asyncpg://app:app_secret@localhost:5432/sppr_orm"
    # URL для интеграционных тестов
    test_database_url: str | None = None
    db_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"

    session_cookie_name: str = "sid"
    session_key_prefix: str = "session:"
    session_ttl_seconds: int = 1800
    session_hard_expire_seconds: int = 43200

    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_path: str = "/"
    cookie_domain: str | None = None

    password_min_length: int = 8
    password_max_length: int = 128

    rate_limit_login_per_minute: int = 5
    rate_limit_register_per_minute: int = 3
    rate_limit_window_seconds: int = 60

    case_materials_storage_dir: str = "./case_materials_storage"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
