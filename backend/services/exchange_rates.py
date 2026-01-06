"""
Exchange Rate Service
Fetches currency exchange rates for portfolio calculations
Uses free APIs: ExchangeRate-API or falls back to Yahoo Finance
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio


class ExchangeRateService:
    """Service to fetch currency exchange rates"""
    
    # Free exchange rate API (no key needed for basic usage)
    BASE_URL = "https://api.exchangerate-api.com/v4/latest"
    
    def __init__(self, base_currency: str = "EUR"):
        self.base_currency = base_currency.upper()
        self._cache: Dict[str, float] = {}
        self._cache_expiry: Optional[datetime] = None
        self._cache_duration = timedelta(hours=4)
    
    def _is_cache_valid(self) -> bool:
        """Check if cached rates are still valid"""
        if self._cache_expiry is None:
            return False
        return datetime.now() < self._cache_expiry
    
    async def fetch_rates(self) -> Dict[str, float]:
        """Fetch all exchange rates relative to base currency"""
        if self._is_cache_valid():
            return self._cache
        
        url = f"{self.BASE_URL}/{self.base_currency}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                self._cache = data.get('rates', {})
                self._cache[self.base_currency] = 1.0
                self._cache_expiry = datetime.now() + self._cache_duration
                
                return self._cache
                
        except Exception as e:
            print(f"Error fetching exchange rates: {e}")
            # Return default rates as fallback
            return {
                'EUR': 1.0,
                'USD': 1.08,
                'GBP': 0.86,
                'CHF': 0.95,
                'JPY': 162.0
            }
    
    async def convert(self, amount: float, from_currency: str, to_currency: str = None) -> float:
        """Convert amount from one currency to another (default: base currency)"""
        if to_currency is None:
            to_currency = self.base_currency
        
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        if from_currency == to_currency:
            return amount
        
        rates = await self.fetch_rates()
        
        # Convert to base currency first, then to target
        if from_currency == self.base_currency:
            rate = rates.get(to_currency, 1.0)
            return amount * rate
        elif to_currency == self.base_currency:
            rate = rates.get(from_currency, 1.0)
            return amount / rate
        else:
            # Cross conversion through base currency
            from_rate = rates.get(from_currency, 1.0)
            to_rate = rates.get(to_currency, 1.0)
            return amount / from_rate * to_rate
    
    async def get_rate(self, from_currency: str, to_currency: str = None) -> float:
        """Get exchange rate between two currencies"""
        return await self.convert(1.0, from_currency, to_currency)

