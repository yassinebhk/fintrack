"""Finnhub API client — insider sentiment (free tier, 60 calls/min).

Best-effort: any failure (missing key, rate limit, unknown ticker) returns
None rather than raising, matching FREDClient's pattern — this is a supporting
signal, never something that should break a scan.

Also only covers US-listed tickers on the free tier (foreign exchanges like
.DE/.MC/.PA/.L/.T answer 403) — expected, not a bug; those simply don't get
an insider judge, same as a stock missing a fundamentals field.
"""

import asyncio
from datetime import datetime, timedelta

import httpx
from loguru import logger

from app.config import get_settings


class FinnhubClient:
    BASE_URL = "https://finnhub.io/api/v1"
    # Free tier caps at 60 calls/min; the scan issues these from many concurrent
    # workers, so without serializing them here they burst past the cap almost
    # immediately and every call after the first ~60 gets a 429. One shared
    # lock + a minimum spacing between requests keeps the whole process under
    # the limit no matter how much concurrency the caller uses.
    _MIN_INTERVAL = 1.1  # seconds -> ~54 calls/min, a safety margin under 60

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.finnhub_api_key
        self._cache: dict[str, dict | None] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._ttl = timedelta(hours=12)
        self._rate_lock = asyncio.Lock()
        self._last_call = 0.0

    async def _throttle(self) -> None:
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            wait = self._MIN_INTERVAL - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = asyncio.get_event_loop().time()

    def _fresh(self, ticker: str) -> bool:
        return ticker in self._cache_expiry and datetime.now() < self._cache_expiry[ticker]

    async def get_insider_sentiment(self, ticker: str) -> dict | None:
        """Latest monthly insider-sentiment reading for `ticker`.

        Returns {"mspr": float, "month": "YYYY-MM", "change": int} or None.
        MSPR (Monthly Share Purchase Ratio) ranges roughly -100..+100 — positive
        means insiders net-bought that month, negative means net-sold.
        """
        if not self.api_key:
            return None
        if self._fresh(ticker):
            return self._cache[ticker]

        try:
            payload = await self._fetch(ticker)
        except Exception as exc:
            logger.warning("Finnhub insider-sentiment fetch failed for {}: {}", ticker, exc)
            return None

        self._cache[ticker] = payload
        self._cache_expiry[ticker] = datetime.now() + self._ttl
        return payload

    async def _fetch(self, ticker: str) -> dict | None:
        today = datetime.now()
        start = (today - timedelta(days=180)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        params = {
            "symbol": ticker,
            "from": start,
            "to": end,
            "token": self.api_key,
        }
        await self._throttle()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.BASE_URL}/stock/insider-sentiment", params=params)
            if resp.status_code == 429:
                logger.warning("Finnhub rate-limited for {}", ticker)
                return None
            if resp.status_code == 403:
                # Free tier: foreign-listed tickers aren't covered. Expected, not an error.
                logger.debug("Finnhub insider-sentiment not available for {} (403, likely non-US listing)", ticker)
                return None
            resp.raise_for_status()
            data = resp.json()

        rows = data.get("data", [])
        if not rows:
            return None
        # Most-recent (year, month) first.
        rows.sort(key=lambda r: (r.get("year", 0), r.get("month", 0)))
        latest = rows[-1]
        mspr = latest.get("mspr")
        if mspr is None:
            return None
        return {
            "mspr": float(mspr),
            "month": f"{latest.get('year')}-{latest.get('month'):02d}",
            "change": latest.get("change"),
        }

    async def get_quote(self, ticker: str) -> dict | None:
        """Live quote for a US-exchange-listed ticker (free tier: pre-market and
        after-hours included, not just the 15:30-22:00 CEST regular session —
        this is what closes the "stale until Wall Street opens" gap Yahoo alone
        has). Foreign listings (anything not on a US exchange, e.g. .DE/.L/.SG)
        answer 403 on the free tier — same as insider-sentiment above, expected,
        not an error; the caller should just fall back to Yahoo for those.

        Returns {"price", "previous_close", "change", "change_percent"} or None."""
        if not self.api_key:
            return None
        try:
            await self._throttle()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/quote", params={"symbol": ticker, "token": self.api_key}
                )
                if resp.status_code in (403, 429):
                    return None
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.debug("Finnhub quote fetch failed for {}: {}", ticker, exc)
            return None

        price = data.get("c")
        prev_close = data.get("pc")
        # A quote for a ticker Finnhub has never traded/heard of still returns
        # 200 with everything zeroed — treat that as "no data", not a real 0 price.
        if not price or not prev_close:
            return None
        return {
            "price": float(price),
            "previous_close": float(prev_close),
            "change": data.get("d"),
            "change_percent": data.get("dp"),
        }
