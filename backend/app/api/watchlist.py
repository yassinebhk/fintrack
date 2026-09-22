"""Watchlist endpoints — track assets you don't own yet and see their live 'setup'
signals (RSI, trend vs SMA200, 52w range, ADX, ATR stop). Direct user actions,
scoped to the logged-in user."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import session_scope
from app.models.user import User
from app.repositories import (
    PositionRepository,
    TransactionRepository,
    WatchlistPinRepository,
    WatchlistRepository,
)
from app.services.market import YahooFinanceService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
_yahoo = YahooFinanceService()


class WatchIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    name: str = Field(default="", max_length=128)
    note: str = Field(default="", max_length=280)


class PinIn(BaseModel):
    note: str | None = Field(default=None, max_length=280)


def _pin_row(p) -> dict:
    return {
        "id": p.id, "ticker": p.ticker,
        "pinned_at": p.pinned_at.isoformat(),
        "price": p.price, "currency": p.currency, "note": p.note,
    }


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


@router.post("/import-history")
async def import_history(current_user: User = Depends(get_current_user)) -> dict:
    """One-off (repeatable) action: seed the watchlist with every ticker you've
    ever bought — current holdings AND fully-exited ones — so past ideas stay
    trackable without re-adding them by hand. Never touches an entry you already
    have (including one you deliberately removed and don't want back): it only
    ADDS tickers missing from the watchlist, never runs automatically."""
    async with session_scope() as s:
        wl_repo = WatchlistRepository(s, current_user.id)
        tx_repo = TransactionRepository(s, current_user.id)
        pos_repo = PositionRepository(s, current_user.id)
        candidates: dict[str, str] = {}
        for t in await tx_repo.list_all():
            candidates.setdefault(t.ticker, "")
        for p in await pos_repo.list_all():
            candidates.setdefault(p.ticker, p.asset_name or "")
        existing = {e.ticker for e in await wl_repo.list_all()}
        added = []
        for ticker, name in candidates.items():
            if ticker not in existing:
                await wl_repo.add(ticker, name)
                added.append(ticker)
        return {"added": added, "count": len(added)}


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


@router.get("/ids")
async def list_watchlist_ids(current_user: User = Depends(get_current_user)) -> dict:
    """Just {id, ticker} for every watchlist entry — no live analysis, so it's
    fast enough to call on every page load to paint the ⭐ button's initial state."""
    async with session_scope() as s:
        entries = await WatchlistRepository(s, current_user.id).list_all()
    return {"items": [{"id": e.id, "ticker": e.ticker} for e in entries]}


@router.post("/{ticker}/pin", status_code=201)
async def pin_ticker(ticker: str, payload: PinIn, current_user: User = Depends(get_current_user)) -> dict:
    """Snapshot this ticker's price right now (captured server-side — more
    trustworthy than whatever stale number the client last rendered), with an
    optional note, so it can be compared against later."""
    quote = await _yahoo.get_price(ticker.upper().strip())
    price = quote.get("price") if quote else None
    currency = quote.get("currency") if quote else None
    async with session_scope() as s:
        pin = await WatchlistPinRepository(s, current_user.id).create(ticker, price, currency, payload.note)
        return _pin_row(pin)


@router.get("/{ticker}/pins")
async def list_pins(ticker: str, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        pins = await WatchlistPinRepository(s, current_user.id).list_for_ticker(ticker)
    return {"items": [_pin_row(p) for p in pins]}


@router.delete("/pins/{pin_id}")
async def delete_pin(pin_id: int, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        ok = await WatchlistPinRepository(s, current_user.id).delete(pin_id)
        if not ok:
            raise HTTPException(status_code=404, detail="No encontrado")
        return {"deleted": True}
