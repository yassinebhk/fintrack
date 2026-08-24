"""CoinGecko prices and history for crypto.

Improvements over legacy:
- Loguru structured logging.
- Crypto id mapping resolved from DB (TickerMappingRepository) with hardcoded fallback.
- Same async API and TTL caching.
"""

import asyncio
from datetime import datetime, timedelta

import httpx
from loguru import logger

from app.db import session_scope
from app.repositories import TickerMappingRepository


HARDCODED_FALLBACK = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
    "PEPE": "pepe",
    "ADA": "cardano",
    "XRP": "ripple",
}


class CoinGeckoService:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        cache_ttl: timedelta = timedelta(minutes=10),
        rate_limit_delay: float = 3.0,
        max_retries: int = 3,
    ) -> None:
        self._cache: dict[str, dict] = {}
        self._expiry: dict[str, datetime] = {}
        self._ttl = cache_ttl
        self._last_request = datetime.min
        self._rate_delay = rate_limit_delay
        self._max_retries = max_retries

    def _fresh(self, key: str) -> bool:
        return key in self._expiry and datetime.now() < self._expiry[key]

    async def _rate_limit(self) -> None:
        elapsed = (datetime.now() - self._last_request).total_seconds()
        if elapsed < self._rate_delay:
            await asyncio.sleep(self._rate_delay - elapsed)
        self._last_request = datetime.now()

    async def _resolve_id(self, ticker: str) -> str:
        upper = ticker.upper()
        try:
            async with session_scope() as s:
                resolved = await TickerMappingRepository(s).resolve(upper)
                if resolved != upper:
                    return resolved
        except Exception as exc:
            logger.debug("crypto id DB lookup failed for {}: {}", upper, exc)
        return HARDCODED_FALLBACK.get(upper, upper.lower())

    async def get_price(self, ticker: str, vs_currency: str = "eur") -> dict | None:
        cache_key = f"{ticker}_{vs_currency}"
        if self._fresh(cache_key):
            return self._cache[cache_key]

        await self._rate_limit()
        coin_id = await self._resolve_id(ticker)
        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if coin_id not in data:
                logger.warning("coingecko no data for {} (id={})", ticker, coin_id)
                return None
            d = data[coin_id]
            price = float(d.get(vs_currency, 0))
            change_24h = float(d.get(f"{vs_currency}_24h_change") or 0)
            result = {
                "ticker": ticker.upper(),
                "price": price,
                "previous_close": price / (1 + change_24h / 100) if change_24h else price,
                "change": price * change_24h / 100 if change_24h else 0,
                "change_percent": change_24h,
                "currency": vs_currency.upper(),
                "market_cap": d.get(f"{vs_currency}_market_cap", 0),
                "volume_24h": d.get(f"{vs_currency}_24h_vol", 0),
                "name": ticker.upper(),
                "last_updated": datetime.now().isoformat(),
            }
            self._cache[cache_key] = result
            self._expiry[cache_key] = datetime.now() + self._ttl
            return result
        except Exception as exc:
            logger.error("coingecko price error for {}: {}", ticker, exc)
            return None

    async def get_prices(self, tickers: list[str], vs_currency: str = "eur") -> dict[str, dict]:
        # Batch request for efficiency
        to_fetch = [t for t in tickers if not self._fresh(f"{t}_{vs_currency}")]
        results = {t: self._cache[f"{t}_{vs_currency}"] for t in tickers if self._fresh(f"{t}_{vs_currency}")}
        if not to_fetch:
            return results

        await self._rate_limit()
        coin_ids = []
        for t in to_fetch:
            coin_ids.append(await self._resolve_id(t))
        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        }

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 429:
                        wait = (attempt + 1) * 10
                        logger.warning("coingecko 429, waiting {}s (attempt {})", wait, attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                for ticker, coin_id in zip(to_fetch, coin_ids):
                    if coin_id not in data:
                        logger.warning("coingecko no data for {} (id={})", ticker, coin_id)
                        continue
                    d = data[coin_id]
                    price = float(d.get(vs_currency, 0))
                    change_24h = float(d.get(f"{vs_currency}_24h_change") or 0)
                    item = {
                        "ticker": ticker.upper(),
                        "price": price,
                        "previous_close": price / (1 + change_24h / 100) if change_24h else price,
                        "change": price * change_24h / 100 if change_24h else 0,
                        "change_percent": change_24h,
                        "currency": vs_currency.upper(),
                        "market_cap": d.get(f"{vs_currency}_market_cap", 0),
                        "name": ticker.upper(),
                        "last_updated": datetime.now().isoformat(),
                    }
                    self._cache[f"{ticker}_{vs_currency}"] = item
                    self._expiry[f"{ticker}_{vs_currency}"] = datetime.now() + self._ttl
                    results[ticker] = item
                break
            except Exception as exc:
                logger.error("coingecko batch error (attempt {}): {}", attempt + 1, exc)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(5)
        return results

    async def get_history(self, ticker: str, days: int = 365, vs_currency: str = "eur") -> list[dict] | None:
        cache_key = f"history_{ticker}_{days}_{vs_currency}"
        if self._fresh(cache_key):
            return self._cache.get(cache_key)

        await self._rate_limit()
        coin_id = await self._resolve_id(ticker)
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": vs_currency,
            "days": str(days),
            "interval": "daily" if days > 1 else "hourly",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    logger.warning("coingecko history rate limited, waiting 60s")
                    await asyncio.sleep(60)
                    resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            prices = data.get("prices", [])
            rows = [
                {
                    "date": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                    "close": float(price),
                    "price": float(price),
                }
                for ts, price in prices
            ]
            # CoinGecko's last point is often an intraday "now" snapshot on top of
            # the daily point for the same day — same date string twice breaks
            # chart libraries that require strictly ascending/unique timestamps.
            # Keep the last (most recent) value per date; order is preserved
            # since duplicates are contiguous and dict keeps first-seen position.
            deduped: dict[str, dict] = {}
            for row in rows:
                deduped[row["date"]] = row
            result = list(deduped.values())
            if result:
                self._cache[cache_key] = result
                self._expiry[cache_key] = datetime.now() + timedelta(minutes=30)
            return result
        except Exception as exc:
            logger.error("coingecko history error for {}: {}", ticker, exc)
            return None
