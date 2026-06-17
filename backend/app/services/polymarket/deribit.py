"""Deribit DVOL — 30-day forward-looking implied volatility for BTC/ETH (public).

DVOL is the option-implied 30d annualized vol: the market's own expectation of
future volatility. For pricing a forward probability it's a better input than
backward-looking realized vol, so we use it for BTC/ETH when available.
Docs: https://docs.deribit.com (public/get_volatility_index_data)
"""

from __future__ import annotations

import time

import httpx
from loguru import logger

BASE = "https://www.deribit.com/api/v2/public"
_SYMBOL_TO_CCY = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}


async def dvol_annualized(symbol: str) -> float | None:
    """Latest DVOL as a fraction (e.g. 0.40 for 40%). None if unavailable."""
    ccy = _SYMBOL_TO_CCY.get(symbol)
    if not ccy:
        return None
    now = int(time.time() * 1000)
    start = now - 3 * 86400 * 1000
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"{BASE}/get_volatility_index_data",
                            params={"currency": ccy, "start_timestamp": start,
                                    "end_timestamp": now, "resolution": 43200})
            r.raise_for_status()
            data = (r.json().get("result") or {}).get("data") or []
        if not data:
            return None
        last_close = float(data[-1][4])   # [ts, open, high, low, close]
        return last_close / 100.0 if last_close > 0 else None
    except Exception as exc:
        logger.warning("deribit DVOL {} failed: {}", ccy, exc)
        return None
