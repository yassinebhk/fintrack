"""Binance public spot prices (no auth needed)."""

import httpx
from loguru import logger


BASE_URL = "https://api.binance.com/api/v3"


class BinanceSpotClient:
    async def get_price(self, symbol: str = "BTCUSDT") -> float | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BASE_URL}/ticker/price", params={"symbol": symbol})
                resp.raise_for_status()
                data = resp.json()
            return float(data["price"])
        except Exception as exc:
            logger.warning("binance price failed for {}: {}", symbol, exc)
            return None

    async def get_prices(self, symbols: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in symbols:
            p = await self.get_price(s)
            if p is not None:
                out[s] = p
        return out

    async def realized_vol_annualized(self, symbol: str = "BTCUSDT", days: int = 90) -> float | None:
        """Annualized realized volatility from daily closes (crypto trades 24/7 → 365)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{BASE_URL}/klines",
                                        params={"symbol": symbol, "interval": "1d", "limit": days + 1})
                resp.raise_for_status()
                kl = resp.json()
            closes = [float(k[4]) for k in kl]
            if len(closes) < 20:
                return None
            import math
            rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
            n = len(rets)
            mean = sum(rets) / n
            var = sum((r - mean) ** 2 for r in rets) / (n - 1)
            return (var ** 0.5) * (365 ** 0.5)
        except Exception as exc:
            logger.warning("binance klines/vol failed for {}: {}", symbol, exc)
            return None

    async def realized_vol_yang_zhang(self, symbol: str = "BTCUSDT", days: int = 60) -> float | None:
        """Annualized Yang-Zhang volatility from daily OHLC — the minimum-variance
        unbiased estimator (~8-14x more efficient than close-to-close). Crypto → 365d."""
        import math
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{BASE_URL}/klines",
                                        params={"symbol": symbol, "interval": "1d", "limit": days + 1})
                resp.raise_for_status()
                kl = resp.json()
            if len(kl) < 20:
                return None
            o, hi, lo, c = ([float(k[j]) for k in kl] for j in (1, 2, 3, 4))
            o, hi, lo, c = list(o), list(hi), list(lo), list(c)
            on, oc, rs = [], [], []   # overnight, open-close, Rogers-Satchell
            for i in range(1, len(kl)):
                if min(o[i], hi[i], lo[i], c[i], c[i - 1]) <= 0:
                    continue
                u = math.log(hi[i] / o[i]); dn = math.log(lo[i] / o[i]); cl = math.log(c[i] / o[i])
                on.append(math.log(o[i] / c[i - 1]))
                oc.append(cl)
                rs.append(u * (u - cl) + dn * (dn - cl))
            n = len(rs)
            if n < 15:
                return None
            mo = sum(on) / n; mc = sum(oc) / n
            var_o = sum((x - mo) ** 2 for x in on) / (n - 1)
            var_c = sum((x - mc) ** 2 for x in oc) / (n - 1)
            var_rs = sum(rs) / n
            k = 0.34 / (1.34 + (n + 1) / (n - 1))
            yz_daily = var_o + k * var_c + (1 - k) * var_rs
            return math.sqrt(max(yz_daily, 0.0) * 365) or None
        except Exception as exc:
            logger.warning("binance yang-zhang vol failed for {}: {}", symbol, exc)
            return None

    async def get_24h_stats(self, symbol: str = "BTCUSDT") -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BASE_URL}/ticker/24hr", params={"symbol": symbol})
                resp.raise_for_status()
                data = resp.json()
            return {
                "symbol": symbol,
                "price": float(data["lastPrice"]),
                "change_pct": float(data["priceChangePercent"]),
                "high": float(data["highPrice"]),
                "low": float(data["lowPrice"]),
                "volume": float(data["volume"]),
            }
        except Exception as exc:
            logger.warning("binance 24h stats failed for {}: {}", symbol, exc)
            return None
