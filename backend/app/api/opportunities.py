"""Opportunity discovery endpoints (AI market analyst)."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.services.opportunities import get_opportunity_service

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

# Reuse the same shared secret as the creators ingest worker.
_INGEST_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


@router.get("")
async def get_opportunities(force: bool = False) -> dict:
    """Today's opportunities. Non-blocking: returns the cached payload instantly, or
    {status:'generating'/'stale'} while a background scan runs (the frontend polls)."""
    try:
        return await get_opportunity_service().peek_or_start(force=force)
    except Exception as exc:
        msg = str(exc)
        logger.exception("opportunities generation failed")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise HTTPException(status_code=503, detail="Cuota LLM agotada; reintenta más tarde.") from exc
        raise HTTPException(status_code=500, detail=msg) from exc


class ScanIn(BaseModel):
    themes: list[dict]
    crypto: list[dict] = []


@router.post("/ingest-scan")
async def ingest_scan(payload: ScanIn, secret: str = "") -> dict:
    """Receive a pre-computed (already scored) universe scan from the GitHub-Actions
    worker — the heavy part runs there (7GB runner) to avoid OOM on the free tier.
    The backend then does the light part: LLM analyst + enrichment + persist."""
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    if not payload.themes:
        raise HTTPException(status_code=400, detail="themes is empty")
    try:
        result = await get_opportunity_service().finalize_from_scan(payload.themes, payload.crypto)
        return {"status": "ok", "opportunities": len(result.get("opportunities", [])),
                "universe_size": result.get("universe_size")}
    except Exception as exc:
        logger.exception("ingest-scan failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
