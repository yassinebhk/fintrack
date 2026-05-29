"""Objective per-holding keep/trim/rotate review (anti-disposition-effect)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.position_review import review_portfolio

router = APIRouter(prefix="/api/positions", tags=["position-review"])


@router.get("/review")
async def get_review() -> dict:
    """Forward-looking signal per holding (HOLD/WATCH/TRIM/ROTATE) with reasons and
    disposition-effect bias flags. Not based on your entry price."""
    try:
        return await review_portfolio()
    except Exception as exc:
        logger.exception("position review failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
