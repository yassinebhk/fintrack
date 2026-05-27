"""Opportunity discovery endpoints (AI market analyst)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.opportunities import get_opportunity_service

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
async def get_opportunities(force: bool = False) -> dict:
    """Today's opportunities. Non-blocking: returns the cached payload instantly, or
    {status:'generating'} while a background scan runs (the frontend polls). This way
    the request never hangs on the ~2-min cold scan."""
    try:
        return await get_opportunity_service().peek_or_start(force=force)
    except Exception as exc:
        msg = str(exc)
        logger.exception("opportunities generation failed")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise HTTPException(status_code=503, detail="Cuota LLM agotada; reintenta más tarde.") from exc
        raise HTTPException(status_code=500, detail=msg) from exc
