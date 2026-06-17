"""Polymarket experiment endpoints (read-only scanner, paper trading only)."""

import os

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.polymarket import BinanceSpotClient, PolymarketScanner

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])
_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


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


# ---------------- Paper-Trading Lab (rigorous, no real money) ----------------

@router.get("/lab/edges")
async def lab_edges(limit: int = Query(default=40, ge=5, le=80)) -> dict:
    """Current model-vs-market edges (does NOT log anything)."""
    from app.services.polymarket import lab
    try:
        edges = await lab.find_edges(limit=limit)
    except Exception as exc:
        logger.exception("polymarket lab edges failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"disclaimer": "Paper trading. Edge = modelo − mercado. Solo estudio.",
            "min_edge": lab.MIN_EDGE, "edges": edges, "count": len(edges)}


@router.get("/lab/report")
async def lab_report() -> dict:
    from app.services.polymarket import lab
    return await lab.report()


@router.get("/lab/ledger")
async def lab_ledger(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    from app.services.polymarket import lab
    data = await lab._load()
    bets = data.get("bets", [])
    return {"total": len(bets), "bets": bets[-limit:][::-1]}


@router.post("/lab/run")
async def lab_run(secret: str = "") -> dict:
    """Log new paper bets for fresh edges + resolve matured ones. Cron + manual."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    from app.services.polymarket import lab
    logged = await lab.log_paper_bets()
    resolved = await lab.evaluate()
    return {"logged": logged, "resolved": resolved}
