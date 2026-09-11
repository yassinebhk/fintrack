"""Polymarket experiment endpoints (read-only scanner is shared; the paper
ledger is scoped to the logged-in user)."""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.auth import get_current_user
from app.models.user import User
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
    """Current model-vs-market edges (does NOT log anything, shared/global)."""
    from app.services.polymarket import lab
    try:
        edges = await lab.find_edges(limit=limit)
    except Exception as exc:
        logger.exception("polymarket lab edges failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"disclaimer": "Paper trading. Edge = modelo − mercado. Solo estudio.",
            "min_edge": lab.MIN_EDGE, "edges": edges, "count": len(edges)}


@router.get("/lab/report")
async def lab_report(current_user: User = Depends(get_current_user)) -> dict:
    from app.services.polymarket import lab
    return await lab.report(current_user.id)


@router.get("/lab/ledger")
async def lab_ledger(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.services.polymarket import lab
    data = await lab._load(current_user.id)
    bets = data.get("bets", [])
    return {"total": len(bets), "bets": bets[-limit:][::-1]}


async def _lab_run_and_digest(user_id: int, send_digest: bool) -> None:
    from app.services.polymarket import lab
    try:
        logged = await lab.log_paper_bets(user_id)
        resolved = await lab.evaluate(user_id)
        if send_digest or (logged.get("new_bets") or 0) > 0 or (resolved.get("resolved_now") or 0) > 0:
            from app.services.notifications.telegram import TelegramNotifier
            await TelegramNotifier().send_html(await lab.telegram_digest(user_id))
    except Exception:
        logger.exception("lab run/digest failed")


@router.post("/lab/run")
async def lab_run(digest: bool = True, current_user: User = Depends(get_current_user)) -> dict:
    """Log new paper bets + resolve matured ones (+ send digest). Runs in background to
    dodge a gateway timeout on the heavy scan."""
    import asyncio
    asyncio.create_task(_lab_run_and_digest(current_user.id, send_digest=digest))
    return {"status": "accepted"}


@router.post("/lab/reset")
async def lab_reset(current_user: User = Depends(get_current_user)) -> dict:
    """Wipe the paper ledger (use after a model fix invalidates old bets)."""
    from app.services.polymarket import lab
    return await lab.reset_ledger(current_user.id)


@router.post("/lab/digest")
async def lab_digest(secret: str = "") -> dict:
    """Owner-only admin/cron trigger (Telegram stays owner-only until Fase 2)."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    import asyncio

    async def _send():
        from app.auth import get_owner_user_id_cached
        from app.services.polymarket import lab
        from app.services.notifications.telegram import TelegramNotifier
        try:
            owner_id = await get_owner_user_id_cached()
            if owner_id is None:
                return
            await TelegramNotifier().send_html(await lab.telegram_digest(owner_id))
        except Exception:
            logger.exception("lab digest send failed")
    asyncio.create_task(_send())
    return {"status": "accepted"}
