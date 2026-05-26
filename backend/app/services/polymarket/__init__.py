"""Polymarket experiment module — paper trading only, isolated from the real portfolio.

IMPORTANT: This module never places real orders. It reads public market data
from Polymarket's Gamma API and compares it with Binance spot to surface
*theoretical* mispricings, recording them as paper signals for study.

The latency-arbitrage edge described in the article requires <50ms execution
infrastructure that a free-tier web service cannot provide. This is an
educational scanner, not a profitable bot.
"""

from app.services.polymarket.binance import BinanceSpotClient
from app.services.polymarket.client import PolymarketClient
from app.services.polymarket.scanner import PolymarketScanner

__all__ = ["BinanceSpotClient", "PolymarketClient", "PolymarketScanner"]
