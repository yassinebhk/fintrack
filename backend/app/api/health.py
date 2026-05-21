"""Health / root endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    settings = get_settings()
    return {
        "status": "online",
        "service": "FinTrack",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "has_gemini": settings.has_gemini,
        "has_kraken": settings.has_kraken,
        "has_telegram": settings.has_telegram,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
