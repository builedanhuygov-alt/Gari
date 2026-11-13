"""
GARI Auth Server 1.0 — Application Configuration
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "GARI Independent Auth Server"
    APP_VERSION: str = "1.0.0"
    AUTH_ENV: str = Field(default="development", description="development | production | testing")
    AUTH_HOST: str = "0.0.0.0"
    AUTH_PORT: int = 8001

    # Database: Default persistent location outside deployment root
    AUTH_DATA_DIR: str = Field(default=str(Path("./data").resolve()))
    AUTH_DB_PATH: str = Field(default="")

    # Session & Cookie Security
    COOKIE_NAME: str = "gari_auth_session"
    CSRF_COOKIE_NAME: str = "gari_csrf_token"
    COOKIE_SECURE: bool = Field(default=False, description="Set True in production with HTTPS")
    COOKIE_SAMESITE: str = "lax"  # lax | strict | none
    COOKIE_DOMAIN: str = ""
    SESSION_TTL_SECONDS: int = 7200  # 2 hours idle timeout
    SESSION_MAX_LIFETIME_SECONDS: int = 86400  # 24 hours absolute maximum

    # Registration Limits (Phase 1 constraint: exactly 10 new accounts)
    MAX_REGISTRATION_ACCOUNTS: int = 10
    REGISTRATION_OPEN: bool = True

    # Security & CORS
    CORS_ALLOWED_ORIGINS: List[str] = [
        "https://gari-team.vercel.app",
        "https://gari-team-fwwp1442f-bui11.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    # One-time Admin Bootstrap Secret (must be provided via environment, never committed)
    BOOTSTRAP_ADMIN_TOKEN: str = ""

    # Rate Limiting
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 60
    RATE_LIMIT_REGISTER_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = 3600

    @property
    def database_url(self) -> str:
        if not self.AUTH_DB_PATH:
            data_dir = Path(self.AUTH_DATA_DIR)
            data_dir.mkdir(parents=True, exist_ok=True)
            db_file = data_dir / "gari_auth.db"
            return f"sqlite:///{db_file.as_posix()}"
        return f"sqlite:///{Path(self.AUTH_DB_PATH).resolve().as_posix()}"


settings = Settings()
