"""Health / status endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api")
@router.get("/api/health")
async def api_status() -> dict:
    """Backend status. `/` is now reserved for the frontend SPA."""
    settings = get_settings()
    from app.db import engine

    return {
        "status": "online",
        "service": "FinTrack",
        "version": __version__,
        "db": engine.dialect.name,  # 'postgresql' = persistente, 'sqlite' = efímero
        "llm_provider": settings.llm_provider,
        "has_gemini": settings.has_gemini,
        "has_groq": settings.has_groq,
        "has_kraken": settings.has_kraken,
        "has_telegram": settings.has_telegram,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
