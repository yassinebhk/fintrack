"""Centralized configuration loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
LOGS_DIR = BACKEND_DIR / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    base_currency: str = "EUR"
    timezone: str = "Europe/Madrid"
    log_level: str = "INFO"

    # LLM
    llm_provider: Literal["gemini", "groq", "anthropic"] = "gemini"
    gemini_api_key: str = ""
    # Defaults aligned with free-tier availability:
    # gemini-2.5-pro is not available on free tier as of 2026 → use 2.5-flash for orchestrator too.
    gemini_model_orchestrator: str = "gemini-2.5-flash"
    gemini_model_agent: str = "gemini-2.5-flash"
    gemini_model_cheap: str = "gemini-2.5-flash-lite"
    gemini_model_fallback: str = "gemini-2.5-flash-lite"
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    # Brokers
    kraken_api_key: str = ""
    kraken_api_secret: str = ""
    tr_phone: str = ""
    tr_pin: str = ""

    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Optional data providers
    fred_api_key: str = ""
    etherscan_api_key: str = ""
    alpha_vantage_api_key: str = ""

    # Database
    database_url: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{DATA_DIR / 'fintrack.db'}"
    )

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_kraken(self) -> bool:
        return bool(self.kraken_api_key and self.kraken_api_secret)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
