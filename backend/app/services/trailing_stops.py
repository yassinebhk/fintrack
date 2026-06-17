"""Trailing-stop sell signals (JsonCache-backed).

For a chosen ticker we track its running PEAK price and fire a CRITICAL Telegram
alert when the price falls `trailing_pct` below that peak — a "the move has rolled
over, consider selling" signal. This is the right tool for things with too little
history for RSI/Sharpe/volatility to mean anything (e.g. a 3-day-old IPO like SPCX):
it needs no statistics, only the peak since we started watching."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

_KEY = "trailing_stops"


async def _load() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        return row.payload if row and row.payload else {"stops": []}
    except Exception as exc:
        logger.warning("trailing_stops load failed: {}", exc)
        return {"stops": []}


async def _save(payload: dict) -> None:
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


async def get_all() -> list[dict]:
    return (await _load()).get("stops", [])


async def set_stop(ticker: str, trailing_pct: float, label: str = "",
                   peak: float | None = None, currency: str = "") -> dict:
    """Create/replace a trailing stop for `ticker`. `peak` seeds the running peak
    (use the current price). Re-arms it (active=True)."""
    ticker = (ticker or "").upper().strip()
    data = await _load()
    stops = [s for s in data.get("stops", []) if (s.get("ticker") or "").upper() != ticker]
    stop = {"ticker": ticker, "trailing_pct": float(trailing_pct),
            "peak": float(peak) if peak else 0.0, "label": label or ticker,
            "currency": currency, "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()}
    stops.append(stop)
    data["stops"] = stops
    await _save(data)
    return stop


async def update_peaks_and_save(stops: list[dict]) -> None:
    """Persist the (possibly updated) stops list back to the cache."""
    await _save({"stops": stops})
