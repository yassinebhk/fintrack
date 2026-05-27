"""Opportunity discovery endpoints (AI market analyst)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.opportunities import get_opportunity_service

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
async def get_opportunities(force: bool = False) -> dict:
    """Today's opportunities (cached 12h; force=true to regenerate)."""
    try:
        return await get_opportunity_service().generate(force=force)
    except Exception as exc:
        msg = str(exc)
        logger.exception("opportunities generation failed")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise HTTPException(status_code=503, detail="Cuota LLM agotada; reintenta más tarde.") from exc
        raise HTTPException(status_code=500, detail=msg) from exc
