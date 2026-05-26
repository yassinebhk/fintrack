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
