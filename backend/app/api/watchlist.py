"""Watchlist endpoints — track assets you don't own yet and see their live 'setup'
signals (RSI, trend vs SMA200, 52w range, ADX, ATR stop). Direct user actions,
scoped to the logged-in user."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import session_scope
from app.models.user import User
from app.repositories import WatchlistRepository

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    name: str = Field(default="", max_length=128)
    note: str = Field(default="", max_length=280)


def _setup(a: dict | None) -> str:
    if not a:
        return "sin datos"
    sig = a.get("signals") or {}
    rsi = sig.get("rsi")
    above = sig.get("above_sma200")
    rng = a.get("range_pos_52w")
    if rsi is not None and rsi < 30:
        return "🟢 Sobreventa (RSI<30)"
    if above and rsi is not None and rsi < 42:
        return "🟢 Pullback en tendencia alcista"
    if rng is not None and rng < 15:
        return "🟡 Cerca de mínimos anuales"
    if above and rng is not None and rng > 85 and rsi is not None and rsi > 55:
        return "🔵 Fuerza / cerca de máximos"
    if above:
        return "En tendencia alcista"
    return "Sin setup claro"


def _row(e, a: dict | None, price: float | None) -> dict:
    sig = (a or {}).get("signals") or {}
    return {
        "id": e.id, "ticker": e.ticker, "name": e.name or e.ticker, "note": e.note,
        "price": price,
        "ret_3m": (a or {}).get("ret_3m"),
        "range_pos_52w": (a or {}).get("range_pos_52w"),
        "rsi": sig.get("rsi"),
        "trend": sig.get("trend"),
        "above_sma200": sig.get("above_sma200"),
        "adx": sig.get("adx"),
        "atr_pct": sig.get("atr_pct"),
        "stop_pct": sig.get("stop_pct"),
        "volume_signal": sig.get("volume_signal"),
        "setup": _setup(a),
    }


@router.get("")
async def list_watchlist(current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        entries = await WatchlistRepository(s, current_user.id).list_all()
    if not entries:
        return {"items": []}
    from app.services.discovery.market_scanner import MarketScanner
    sc = MarketScanner()
    sem = asyncio.Semaphore(5)

    async def one(e):
        a = price = None
        try:
            a = await sc._analyze_ticker(e.ticker, e.name or e.ticker, "watchlist", sem, fetch_price=False)
            p = await sc.yahoo.get_price(e.ticker)
            price = p.get("price") if p else None
        except Exception:
            pass
        return _row(e, a, price)

    rows = await asyncio.gather(*[one(e) for e in entries])
    return {"items": rows}


@router.post("", status_code=201)
async def add_watchlist(payload: WatchIn, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        e = await WatchlistRepository(s, current_user.id).add(payload.ticker, payload.name, payload.note)
        return {"id": e.id, "ticker": e.ticker, "name": e.name, "note": e.note}


@router.delete("/{entry_id}")
async def delete_watchlist(entry_id: int, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        ok = await WatchlistRepository(s, current_user.id).delete(entry_id)
        if not ok:
            raise HTTPException(status_code=404, detail="No encontrado")
        return {"deleted": True}
