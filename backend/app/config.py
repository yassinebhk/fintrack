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
    # Additional free OpenAI-compatible providers for the fallback chain.
    openrouter_api_key: str = ""
    cerebras_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    cerebras_model: str = "gpt-oss-120b"  # verified available on the account (llama-3.3-70b → 404)

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
    def async_database_url(self) -> str:
        """Normalize the DB URL to an async driver.

        Render's Postgres URL comes as `postgres://...` or `postgresql://...`;
        SQLAlchemy async needs `postgresql+asyncpg://...`.
        """
        url = self.database_url
        # CockroachDB needs SQLAlchemy's cockroachdb dialect (the plain postgresql
        # asyncpg dialect breaks on its JSON type: "unknown type: pg_catalog.json").
        is_crdb = "cockroachlabs.cloud" in url or url.startswith("cockroachdb")
        driver = "cockroachdb+asyncpg" if is_crdb else "postgresql+asyncpg"
        for prefix in ("postgresql://", "postgres://", "cockroachdb://"):
            if url.startswith(prefix):
                url = f"{driver}://" + url[len(prefix):]
                break
        # Strip query params libpq/asyncpg-cli understand but the asyncpg DBAPI
        # connect() doesn't accept as kwargs (SSL is set via connect_args in
        # db.py instead). Neon's copy-paste connection string orders
        # channel_binding before sslmode, so a plain "?sslmode=" split misses it.
        if "?" in url:
            base, _, query = url.partition("?")
            from urllib.parse import parse_qsl, urlencode

            kept = [(k, v) for k, v in parse_qsl(query) if k not in {"sslmode", "channel_binding"}]
            url = base + (f"?{urlencode(kept)}" if kept else "")
        return url

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
