"""Polymarket experiment endpoints (read-only scanner, paper trading only)."""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.polymarket import BinanceSpotClient, PolymarketScanner

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])


@router.get("/scan")
async def scan(limit: int = Query(default=20, ge=1, le=50)) -> dict:
    """Scan active crypto markets and surface theoretical mispricings vs Binance spot."""
    try:
        result = await PolymarketScanner().scan(limit=limit)
    except Exception as exc:
        logger.exception("polymarket scan failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "disclaimer": "Experimental. Solo lectura y paper trading — no se colocan órdenes reales.",
        **result,
    }


@router.get("/binance/{symbol}")
async def binance_price(symbol: str) -> dict:
    stats = await BinanceSpotClient().get_24h_stats(symbol.upper())
    if stats is None:
        raise HTTPException(status_code=404, detail=f"No Binance data for {symbol}")
    return stats
