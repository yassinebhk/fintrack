"""Yahoo Finance prices for stocks / ETFs / funds.

Improvements over legacy:
- Loguru structured logging instead of prints.
- Ticker mapping resolved from DB (TickerMappingRepository), with hardcoded fallback for first boot.
- Async-first, with thread-pool fallback to yfinance when the direct API fails.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
import yfinance as yf
from loguru import logger

from app.db import session_scope
from app.repositories import TickerMappingRepository


HARDCODED_FALLBACK: dict[str, str] = {
    "LYX0F.DE": "UST.PA",
    "IE00BYX5NX33": "0P0001CLDK.F",
    "SGLD.L": "PPFB.DE",
    "IE00B4ND3602": "PPFB.DE",
}

YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


class YahooFinanceService:
    BASE_URL = "https://query1.finance.yahoo.com"

    def __init__(self, cache_ttl: timedelta = timedelta(minutes=15)) -> None:
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._cache: dict[str, dict] = {}
        self._expiry: dict[str, datetime] = {}
        self._ttl = cache_ttl

    def _fresh(self, key: str) -> bool:
        return key in self._expiry and datetime.now() < self._expiry[key]

    async def _resolve_ticker(self, ticker: str) -> str:
        try:
            async with session_scope() as s:
                resolved = await TickerMappingRepository(s).resolve(ticker)
                if resolved != ticker:
                    return resolved
        except Exception as exc:
            logger.debug("ticker mapping DB lookup failed for {}: {}", ticker, exc)
        return HARDCODED_FALLBACK.get(ticker, ticker)

    async def _fetch_api(self, ticker: str) -> dict | None:
        mapped = await self._resolve_ticker(ticker)
        url = f"{self.BASE_URL}/v8/finance/chart/{mapped}"
        params = {"interval": "1d", "range": "5d"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=YAHOO_HEADERS, params=params)
                if resp.status_code != 200:
                    logger.warning("yahoo API {} -> HTTP {}", ticker, resp.status_code)
                    return None
                payload = resp.json()
                result = payload.get("chart", {}).get("result")
                if not result:
                    err = payload.get("chart", {}).get("error", {})
                    logger.warning("yahoo no data for {} (mapped={}): {}", ticker, mapped, err.get("description", "?"))
                    return None
                meta = result[0].get("meta", {})
                current = float(meta.get("regularMarketPrice") or 0)
                prev = float(meta.get("chartPreviousClose") or current)
                return {
                    "ticker": ticker,
                    "price": current,
                    "previous_close": prev,
                    "change": current - prev,
                    "change_percent": ((current - prev) / prev * 100) if prev else 0.0,
                    "currency": meta.get("currency", "EUR"),
                    "name": meta.get("shortName") or meta.get("longName") or ticker,
                    "market_cap": 0,
                    "last_updated": datetime.now().isoformat(),
                }
        except Exception as exc:
            logger.error("yahoo API error for {}: {}", ticker, exc)
            return None

    def _fetch_yfinance_sync(self, ticker: str, mapped: str) -> dict | None:
        try:
            stock = yf.Ticker(mapped)
            info = stock.info
            hist = stock.history(period="1d")
            if hist.empty and not info.get("regularMarketPrice"):
                return None
            current = float(hist["Close"].iloc[-1]) if not hist.empty else float(info.get("regularMarketPrice", 0))
            prev = float(info.get("previousClose", current))
            return {
                "ticker": ticker,
                "price": current,
                "previous_close": prev,
                "change": current - prev,
                "change_percent": ((current - prev) / prev * 100) if prev else 0.0,
                "currency": info.get("currency", "USD"),
                "name": info.get("shortName", ticker),
                "market_cap": info.get("marketCap", 0),
                "last_updated": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("yfinance fallback failed for {}: {}", ticker, exc)
            return None

    async def get_price(self, ticker: str) -> dict | None:
        if self._fresh(ticker):
            return self._cache[ticker]
        result = await self._fetch_api(ticker)
        if not result:
            mapped = await self._resolve_ticker(ticker)
            logger.info("falling back to yfinance for {}", ticker)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._fetch_yfinance_sync, ticker, mapped)
        if result:
            self._cache[ticker] = result
            self._expiry[ticker] = datetime.now() + self._ttl
        return result

    async def get_prices(self, tickers: list[str]) -> dict[str, dict]:
        results = await asyncio.gather(*(self.get_price(t) for t in tickers))
        return {t: r for t, r in zip(tickers, results) if r}

    async def _fetch_history_api(self, ticker: str, period: str = "1y") -> list[dict] | None:
        mapped = await self._resolve_ticker(ticker)
        url = f"{self.BASE_URL}/v8/finance/chart/{mapped}"
        params = {"interval": "1d", "range": period}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=YAHOO_HEADERS, params=params)
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                result = payload.get("chart", {}).get("result")
                if not result:
                    return None
                ts = result[0].get("timestamp", [])
                quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
                history = []
                for i, t in enumerate(ts):
                    close = (quotes.get("close") or [])[i] if i < len(quotes.get("close", [])) else None
                    if close is None:
                        continue
                    history.append({
                        "date": datetime.fromtimestamp(t).strftime("%Y-%m-%d"),
                        "open": (quotes.get("open") or [close])[i] or close,
                        "high": (quotes.get("high") or [close])[i] or close,
                        "low": (quotes.get("low") or [close])[i] or close,
                        "close": close,
                        "volume": (quotes.get("volume") or [0])[i] or 0,
                    })
                return history or None
        except Exception as exc:
            logger.error("yahoo history error for {}: {}", ticker, exc)
            return None

    async def get_history(self, ticker: str, period: str = "1y") -> list[dict] | None:
        key = f"history_{ticker}_{period}"
        if self._fresh(key):
            return self._cache.get(key)
        result = await self._fetch_history_api(ticker, period)
        if result:
            self._cache[key] = result
            self._expiry[key] = datetime.now() + timedelta(minutes=30)
        return result
