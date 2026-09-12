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

    FUNDAMENTAL_FIELDS = (
        "trailingPE", "forwardPE", "priceToBook", "pegRatio",
        "returnOnEquity", "returnOnAssets", "operatingMargins", "profitMargins",
        "freeCashflow", "revenueGrowth", "earningsGrowth",
        "debtToEquity", "currentRatio", "dividendYield", "marketCap",
        "sector", "industry",
    )

    # Plausibility bounds — Yahoo occasionally returns garbage (wrong unit / scale,
    # e.g. a margin of 95.95 instead of 0.9595). A value outside its range is
    # DROPPED (that judge simply doesn't vote for this name) rather than trusted or
    # zero-filled. Margins/growth/ROE are fractions (0.30 = 30%); PE/PB/PEG ratios;
    # debtToEquity a percentage-style figure; dividendYield already a percent.
    # freeCashflow is unbounded (can be legitimately negative). No bound = no check.
    _FUND_BOUNDS = {
        "trailingPE": (0.0, 300.0), "forwardPE": (0.0, 300.0),
        "priceToBook": (0.0, 100.0), "pegRatio": (0.0, 20.0),
        "returnOnEquity": (-2.0, 5.0), "returnOnAssets": (-1.0, 1.5),
        "operatingMargins": (-2.0, 1.5), "profitMargins": (-2.0, 1.5),
        "revenueGrowth": (-1.0, 10.0), "earningsGrowth": (-1.0, 20.0),
        "debtToEquity": (0.0, 2000.0), "currentRatio": (0.0, 100.0),
        "dividendYield": (0.0, 30.0), "marketCap": (0.0, float("inf")),
    }

    async def get_fundamentals(self, ticker: str) -> dict | None:
        """Fundamental ratios for a STOCK via yfinance `.get_info()`. Best-effort:
        returns the fields present AND plausible (partial for banks/REITs — they
        lack FCF / currentRatio, etc.), or None for non-equities and failures.
        Network-heavy and slow — meant for the daily GitHub-Actions universe scan,
        NOT the request hot path. Cached 12h (fundamentals barely move intraday)."""
        key = f"fund:{ticker.upper()}"
        if self._fresh(key):
            return self._cache.get(key)

        def _work() -> dict | None:
            try:
                info = yf.Ticker(ticker).get_info()
            except Exception as exc:
                logger.debug("fundamentals for {} failed: {}", ticker, exc)
                return None
            if not info or info.get("quoteType") != "EQUITY":
                return None
            out: dict = {}
            for f in self.FUNDAMENTAL_FIELDS:
                v = info.get(f)
                if v is None:
                    continue
                bounds = self._FUND_BOUNDS.get(f)
                if bounds is not None:  # numeric field with a sanity range
                    try:
                        if not (bounds[0] <= float(v) <= bounds[1]):
                            continue  # implausible → drop (garbage in Yahoo's data)
                    except (TypeError, ValueError):
                        continue
                out[f] = v
            return out or None

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(self._executor, _work)
        self._cache[key] = res
        self._expiry[key] = datetime.now() + timedelta(hours=12)
        return res

    async def get_bond_metrics(self, ticker: str) -> dict | None:
        """Bond-ETF metrics via yfinance `.get_info()`: distribution `yield`, the
        Morningstar `category` (a duration/credit bucket, e.g. 'Long Government'),
        `beta3Year` (rate-sensitivity proxy — long-duration funds run high) and YTD.
        Good for US-listed bond ETFs; EU UCITS bond ETFs are data-poor on Yahoo and
        usually return None. Cached 12h."""
        key = f"bond:{ticker.upper()}"
        if self._fresh(key):
            return self._cache.get(key)

        def _work() -> dict | None:
            try:
                info = yf.Ticker(ticker).get_info()
            except Exception as exc:
                logger.debug("bond metrics for {} failed: {}", ticker, exc)
                return None
            if not info or info.get("quoteType") != "ETF":
                return None
            out: dict = {}
            y = info.get("yield")
            try:
                # >0, not >=0: accumulating UCITS ETFs report 0.0 (they reinvest
                # instead of distributing), which is missing data, not a real 0% carry.
                if y is not None and 0.0 < float(y) <= 0.30:  # sane distribution yield
                    out["yield"] = float(y)
            except (TypeError, ValueError):
                pass
            # ytdReturn is left out on purpose: Yahoo returns it on an inconsistent
            # scale across bond ETFs (some fraction, some already-percent → garbage
            # like -288%), so it's not trustworthy enough to show.
            for f in ("category", "beta3Year", "totalAssets"):
                v = info.get(f)
                if v is not None:
                    out[f] = v
            return out or None

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(self._executor, _work)
        self._cache[key] = res
        self._expiry[key] = datetime.now() + timedelta(hours=12)
        return res

    async def get_catalysts(self, ticker: str) -> dict | None:
        """Upcoming per-asset catalysts via yfinance `.calendar`: next earnings date,
        ex-dividend and dividend-payment dates (ISO strings). Mostly populated for
        stocks; ETFs usually return nothing. Uses `.calendar` (no lxml needed).
        Cached 12h."""
        key = f"cat:{ticker.upper()}"
        if self._fresh(key):
            return self._cache.get(key)

        def _work() -> dict | None:
            try:
                cal = yf.Ticker(ticker).calendar
            except Exception as exc:
                logger.debug("catalysts for {} failed: {}", ticker, exc)
                return None
            if not isinstance(cal, dict) or not cal:
                return None
            out: dict = {}
            ed = cal.get("Earnings Date")
            if isinstance(ed, (list, tuple)):
                ed = ed[0] if ed else None
            if ed is not None:
                out["earnings"] = ed.isoformat() if hasattr(ed, "isoformat") else str(ed)
            for src, name in (("Ex-Dividend Date", "ex_dividend"), ("Dividend Date", "dividend")):
                v = cal.get(src)
                if v is not None:
                    out[name] = v.isoformat() if hasattr(v, "isoformat") else str(v)
            return out or None

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(self._executor, _work)
        self._cache[key] = res
        self._expiry[key] = datetime.now() + timedelta(hours=12)
        return res

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
                # Harden previous_close: Yahoo's meta.chartPreviousClose occasionally
                # returns a corrupt value (seen ~12% off for JEDI), which produced
                # spurious day-change %s and risked false "asset cae/sube X%" alerts.
                # The daily close series is the ground truth, so derive prev from it
                # and only fall back to the meta field when the series is unavailable.
                try:
                    closes = [c for c in (result[0].get("indicators", {})
                              .get("quote", [{}])[0].get("close") or []) if c is not None]
                except Exception:
                    closes = []
                prev = 0.0
                if closes:
                    # If the last daily bar is today's (≈ current), the previous close
                    # is the bar before it; otherwise the last bar IS the prior close.
                    if len(closes) >= 2 and current > 0 and abs(current / closes[-1] - 1) < 0.01:
                        prev = float(closes[-2])
                    else:
                        prev = float(closes[-1])
                meta_prev = float(meta.get("chartPreviousClose") or 0)
                if prev <= 0:
                    prev = meta_prev or current
                elif meta_prev > 0 and abs(meta_prev / prev - 1) > 0.08:
                    logger.warning("yahoo {}: chartPreviousClose={:.4f} disagrees with series close={:.4f}; using series",
                                   ticker, meta_prev, prev)
                if not current:
                    current = prev
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
