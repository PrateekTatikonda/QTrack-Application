"""Application settings, loaded once from environment variables and ``backend/.env``."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,*"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_description: str
    app_version: str
    log_level: str

    db_user: str | None
    db_password: str | None
    db_host: str | None
    db_port: str | None
    db_name: str | None

    redis_host: str
    redis_port: int
    redis_password: str | None

    cors_origins: list[str]

    groq_api_key: str | None
    ai_model: str
    medical_services: list[str]
    # Base URL the AI agent uses to call the queue API.
    internal_api_base_url: str

    whatsapp_access_token: str | None
    whatsapp_phone_number_id: str | None
    whatsapp_verify_token: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name="QTrack API",
            app_description="AI-Powered Hospital Queue Management System",
            app_version="2.0.0",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            db_user=os.getenv("DB_USER"),
            db_password=os.getenv("DB_PASSWORD"),
            db_host=os.getenv("DB_HOST"),
            db_port=os.getenv("DB_PORT"),
            db_name=os.getenv("DB_NAME"),
            redis_host=os.getenv("REDIS_HOST") or "localhost",
            redis_port=int(os.getenv("REDIS_PORT") or 6379),
            redis_password=os.getenv("REDIS_PASSWORD") or None,
            cors_origins=_csv(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            ai_model=os.getenv("AI_MODEL", "qwen/qwen3.8-27b"),
            medical_services=[s.lower() for s in _csv(os.getenv("MEDICAL_SERVICES", "general,emergency"))],
            internal_api_base_url=os.getenv("INTERNAL_API_BASE_URL", "http://localhost:8000"),
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN") or None,
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID") or None,
            whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", "qtrack_verify_token"),
        )


settings = Settings.from_env()
