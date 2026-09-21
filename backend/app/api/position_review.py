"""Objective per-holding keep/trim/rotate review (anti-disposition-effect)."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import User
from app.services.position_review import review_portfolio, set_horizon

router = APIRouter(prefix="/api/positions", tags=["position-review"])


@router.get("/review")
async def get_review(force: bool = False, current_user: User = Depends(get_current_user)) -> dict:
    """Forward-looking signal per holding (HOLD/WATCH/TRIM/ROTATE) with reasons and
    disposition-effect bias flags. Not based on your entry price. Horizon-aware
    (largo/medio/corto). Cached 6h per user; force=true recomputes.

    2026-09-21 security fix: this used to always compute (and cache under one
    global key) the OWNER's portfolio regardless of who was logged in — any
    signed-in user saw the owner's real positions and P&L. Now scoped to
    current_user.id end to end (service call + cache key)."""
    try:
        return await review_portfolio(current_user.id, force=force)
    except Exception as exc:
        logger.exception("position review failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class HorizonIn(BaseModel):
    ticker: str
    horizon: str  # largo | medio | corto


@router.post("/review/horizon")
async def set_position_horizon(payload: HorizonIn, current_user: User = Depends(get_current_user)) -> dict:
    """Set the holding horizon for a position (changes how sell signals are read)."""
    try:
        res = await set_horizon(current_user.id, payload.ticker, payload.horizon)
        return {"ok": True, **res}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("set horizon failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
