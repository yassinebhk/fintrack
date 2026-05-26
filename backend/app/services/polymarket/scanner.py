"""Scanner: surfaces theoretical mispricings between Polymarket and Binance.

This is a study tool. For each active crypto market it pulls the implied
probability (the YES price) and reports it alongside Binance spot context.
It does NOT execute trades and makes no profitability claims.
"""

import re
from datetime import datetime, timezone

from loguru import logger

from app.services.polymarket.binance import BinanceSpotClient
from app.services.polymarket.client import PolymarketClient


# Keyword → Binance symbol, matched with word boundaries (order matters).
SYMBOL_HINTS = [
    (r"\bbitcoin\b", "BTCUSDT"),
    (r"\bbtc\b", "BTCUSDT"),
    (r"\bethereum\b", "ETHUSDT"),
    (r"\beth\b", "ETHUSDT"),
    (r"\bsolana\b", "SOLUSDT"),
    (r"\bsol\b", "SOLUSDT"),
    (r"\bdogecoin\b", "DOGEUSDT"),
    (r"\bdoge\b", "DOGEUSDT"),
]

# Price patterns require a $ or k/M marker so we don't mistake a year (2026) for a strike.
PRICE_PATTERNS = [
    re.compile(r"\$\s*([0-9][0-9,\.]*)\s*([kKmM])\b"),   # $150k, $1.5M
    re.compile(r"\$\s*([0-9][0-9,\.]{2,})"),              # $85,000
    re.compile(r"\b([0-9][0-9,\.]*)\s*([kKmM])\b"),       # 150k (no $)
]

MULTIPLIERS = {"k": 1_000, "m": 1_000_000}


class PolymarketScanner:
    def __init__(self) -> None:
        self.poly = PolymarketClient()
        self.binance = BinanceSpotClient()

    def _detect_symbol(self, question: str) -> str | None:
        q = question.lower()
        best_pos = None
        best_sym = None
        for pattern, sym in SYMBOL_HINTS:
            m = re.search(pattern, q)
            if m and (best_pos is None or m.start() < best_pos):
                best_pos = m.start()
                best_sym = sym
        return best_sym

    def _extract_target_price(self, question: str) -> float | None:
        for pat in PRICE_PATTERNS:
            m = pat.search(question)
            if not m:
                continue
            raw = m.group(1).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            has_suffix = m.lastindex and m.lastindex >= 2 and m.group(2)
            if has_suffix:
                value *= MULTIPLIERS.get(m.group(2).lower(), 1)
            return value
        return None

    async def scan(self, limit: int = 20) -> dict:
        markets = await self.poly.search_crypto_markets(limit=limit)
        if not markets:
            return {"markets": [], "binance": {}, "scanned_at": datetime.now(timezone.utc).isoformat()}

        # Gather the binance symbols we need
        needed: set[str] = set()
        for m in markets:
            sym = self._detect_symbol(m.get("question") or "")
            if sym:
                needed.add(sym)
        binance_prices = await self.binance.get_prices(list(needed)) if needed else {}

        enriched = []
        for m in markets:
            question = m.get("question") or ""
            symbol = self._detect_symbol(question)
            spot = binance_prices.get(symbol) if symbol else None
            target = self._extract_target_price(question)

            yes_price = None
            for o in m.get("outcomes", []):
                if str(o.get("outcome", "")).lower() in ("yes", "sí", "si", "up"):
                    yes_price = o.get("price")
                    break
            if yes_price is None and m.get("outcomes"):
                yes_price = m["outcomes"][0].get("price")

            # Theoretical note: if the question is "Will X be above $T" and spot already
            # crossed T decisively, the implied probability should be near 0/1.
            note = None
            if spot and target:
                distance_pct = (spot - target) / target * 100
                if abs(distance_pct) < 0.5:
                    note = "Spot está muy cerca del strike — alta sensibilidad"
                elif distance_pct > 2 and yes_price is not None and yes_price < 0.9:
                    note = f"Spot {distance_pct:+.1f}% sobre strike pero YES a {yes_price:.2f} (posible rezago)"
                elif distance_pct < -2 and yes_price is not None and yes_price > 0.1:
                    note = f"Spot {distance_pct:+.1f}% bajo strike pero YES a {yes_price:.2f} (posible rezago)"

            enriched.append({
                **m,
                "binance_symbol": symbol,
                "binance_spot": spot,
                "target_price": target,
                "yes_price": yes_price,
                "implied_probability_pct": round(yes_price * 100, 1) if yes_price is not None else None,
                "note": note,
            })

        return {
            "markets": enriched,
            "binance": binance_prices,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
