"""Out-of-sample scorecard of the recommendation engine (honesty backbone)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services import scorecard as sc

router = APIRouter(prefix="/api/scorecard", tags=["scorecard"])


@router.get("")
async def get_scorecard() -> dict:
    """How the engine's past recommendations actually performed (1m/3m/6m)."""
    try:
        return await sc.summary()
    except Exception as exc:
        logger.exception("scorecard summary failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/equity-curve")
async def get_equity_curve() -> dict:
    """Cumulative average alpha over time from evaluated recommendations."""
    try:
        return await sc.equity_curve()
    except Exception as exc:
        logger.exception("scorecard equity curve failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/evaluate")
async def evaluate() -> dict:
    """Manually evaluate matured recommendations (also runs daily on a cron)."""
    try:
        n = await sc.evaluate_due()
        return {"evaluated_points": n}
    except Exception as exc:
        logger.exception("scorecard evaluate failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
