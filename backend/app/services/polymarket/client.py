"""Polymarket Gamma API client (public, read-only).

Docs: https://docs.polymarket.com/  (Gamma markets API)
We only read market metadata + current prices; no trading.
"""

import httpx
from loguru import logger


GAMMA_URL = "https://gamma-api.polymarket.com"


class PolymarketClient:
    async def get_markets(
        self,
        *,
        closed: bool = False,
        limit: int = 50,
        offset: int = 0,
        tag: str | None = None,
    ) -> list[dict]:
        """Fetch active markets. Gamma caps each call at 100, so callers paginate
        via `offset`. Optionally filter by a tag like 'crypto'."""
        params: dict = {"closed": str(closed).lower(), "limit": limit, "offset": offset,
                        "order": "volume24hr", "ascending": "false"}
        if tag:
            params["tag_id"] = tag
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{GAMMA_URL}/markets", params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("polymarket markets fetch failed: {}", exc)
            return []
        if isinstance(data, dict):
            data = data.get("data", [])
        return data or []

    async def get_market_by_id(self, market_id: str) -> dict | None:
        """Fetch a single market by id (used to check resolution of a paper bet).
        Returns the normalized market plus raw `closed`/resolution fields."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{GAMMA_URL}/markets/{market_id}")
                resp.raise_for_status()
                m = resp.json()
        except Exception as exc:
            logger.warning("polymarket market {} fetch failed: {}", market_id, exc)
            return None
        if isinstance(m, list):
            m = m[0] if m else None
        if not m:
            return None
        norm = self._normalize_market(m)
        norm["closed"] = bool(m.get("closed"))
        norm["umaResolutionStatus"] = m.get("umaResolutionStatus")
        return norm

    async def search_crypto_markets(self, limit: int = 30, pages: int = 6) -> list[dict]:
        """Pull active markets and keep the ones genuinely about crypto prices.

        Crypto price markets aren't in the top-100 by volume, and Gamma caps each
        call at 100, so we PAGINATE (offset) across several pages. Word-boundary
        matching avoids 'Ethan'→'eth'; a price token ($/k/price/hit/above/…) filters
        out sports/politics noise.
        """
        import re

        crypto_re = re.compile(
            r"\b(bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge)\b",
            re.IGNORECASE,
        )
        price_signal_re = re.compile(
            r"(\$|\bprice\b|\bhit\b|\breach\b|\babove\b|\bbelow\b|\bk\b|all[- ]time high|\bath\b)",
            re.IGNORECASE,
        )
        result: list[dict] = []
        seen: set = set()
        for p in range(pages):
            batch = await self.get_markets(closed=False, limit=100, offset=p * 100)
            if not batch:
                break
            for m in batch:
                question = m.get("question") or m.get("title") or ""
                mid = m.get("id")
                if mid in seen:
                    continue
                if crypto_re.search(question) and price_signal_re.search(question):
                    seen.add(mid)
                    result.append(self._normalize_market(m))
                    if len(result) >= limit:
                        return result
        return result

    def _normalize_market(self, m: dict) -> dict:
        # Parse outcome prices (Gamma returns them as a JSON string sometimes)
        import json
        outcomes = m.get("outcomes")
        prices = m.get("outcomePrices")
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except json.JSONDecodeError:
                outcomes = []
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except json.JSONDecodeError:
                prices = []
        outcome_data = []
        for i, o in enumerate(outcomes or []):
            price = None
            try:
                price = float(prices[i]) if prices and i < len(prices) else None
            except (ValueError, TypeError):
                price = None
            outcome_data.append({"outcome": o, "price": price})

        return {
            "id": m.get("id"),
            "question": m.get("question") or m.get("title"),
            "slug": m.get("slug"),
            "end_date": m.get("endDate"),
            "volume_24h": m.get("volume24hr") or m.get("volume24hrClob"),
            "liquidity": m.get("liquidity"),
            "outcomes": outcome_data,
            "url": f"https://polymarket.com/event/{m.get('slug')}" if m.get("slug") else None,
        }
