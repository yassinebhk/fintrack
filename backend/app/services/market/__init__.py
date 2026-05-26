"""Market data providers."""

from app.services.market.coingecko import CoinGeckoService
from app.services.market.ecb import ECBClient
from app.services.market.economic_calendar import upcoming_events
from app.services.market.exchange_rates import ExchangeRateService
from app.services.market.fred import FREDClient
from app.services.market.yahoo_finance import YahooFinanceService

__all__ = [
    "CoinGeckoService",
    "ECBClient",
    "ExchangeRateService",
    "FREDClient",
    "YahooFinanceService",
    "upcoming_events",
]
