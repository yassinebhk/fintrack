"""FX rates from ECB SDW (free, official) with exchangerate-api.com fallback."""

from datetime import datetime, timedelta

import httpx
from loguru import logger


ECB_URL = "https://api.frankfurter.app"  # free wrapper around ECB reference rates
FALLBACK_URL = "https://api.exchangerate-api.com/v4/latest"


class ExchangeRateService:
    def __init__(self, base_currency: str = "EUR", cache_ttl: timedelta = timedelta(hours=4)) -> None:
        self.base = base_currency.upper()
        self._rates: dict[str, float] = {self.base: 1.0}
        self._expiry: datetime | None = None
        self._ttl = cache_ttl

    def _fresh(self) -> bool:
        return self._expiry is not None and datetime.now() < self._expiry

    async def _fetch_ecb(self) -> dict[str, float] | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{ECB_URL}/latest", params={"from": self.base})
                resp.raise_for_status()
                rates = resp.json().get("rates", {})
                rates[self.base] = 1.0
                return rates
        except Exception as exc:
            logger.warning("ECB fx fetch failed: {}", exc)
            return None

    async def _fetch_fallback(self) -> dict[str, float] | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{FALLBACK_URL}/{self.base}")
                resp.raise_for_status()
                rates = resp.json().get("rates", {})
                rates[self.base] = 1.0
                return rates
        except Exception as exc:
            logger.warning("fallback fx fetch failed: {}", exc)
            return None

    async def fetch_rates(self) -> dict[str, float]:
        if self._fresh():
            return self._rates
        rates = await self._fetch_ecb() or await self._fetch_fallback()
        if rates:
            self._rates = rates
            self._expiry = datetime.now() + self._ttl
        else:
            logger.error("could not fetch fx rates from any provider, using stale/defaults")
            if not self._rates or len(self._rates) <= 1:
                self._rates = {
                    "EUR": 1.0, "USD": 1.08, "GBP": 0.86, "CHF": 0.95, "JPY": 162.0,
                }
        return self._rates

    async def convert(self, amount: float, from_currency: str, to_currency: str | None = None) -> float:
        to_currency = (to_currency or self.base).upper()
        from_currency = from_currency.upper()
        if from_currency == to_currency:
            return amount
        rates = await self.fetch_rates()
        if from_currency == self.base:
            return amount * rates.get(to_currency, 1.0)
        if to_currency == self.base:
            return amount / rates.get(from_currency, 1.0)
        return amount / rates.get(from_currency, 1.0) * rates.get(to_currency, 1.0)

    async def get_rate(self, from_currency: str, to_currency: str | None = None) -> float:
        return await self.convert(1.0, from_currency, to_currency)
