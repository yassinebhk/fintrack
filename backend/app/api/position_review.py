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
    (largo/medio/corto). Cached 6h; force=true recomputes.

    NOTE (Fase 1): still computes the OWNER's portfolio regardless of who's
    logged in, same as Kraken sync / Telegram / the monthly contribution — not
    yet generalized per-user. This dependency only closes the bigger hole: the
    route had no login requirement at all, so anyone with the URL could read
    real P&L figures without ever signing in."""
    try:
        return await review_portfolio(force=force)
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
        res = await set_horizon(payload.ticker, payload.horizon)
        return {"ok": True, **res}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("set horizon failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
