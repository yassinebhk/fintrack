"""Deep per-asset analysis endpoint (web modal + Telegram /analizar)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.asset_analysis import analyze_asset

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{ticker}/deep-analysis")
async def deep_analysis(ticker: str) -> dict:
    """Comprehensive analysis of a single asset (metrics, ensemble breakdown,
    multiple charts, multi-source news with sentiment, broker-style narrative)."""
    try:
        return await analyze_asset(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("deep analysis failed for {}", ticker)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
# trigger redeploy (1779992522)
