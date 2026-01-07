"""
CoinGecko Service
Fetches cryptocurrency prices using CoinGecko API (free, no API key required)
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio


# Mapping common crypto tickers to CoinGecko IDs
CRYPTO_ID_MAP = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'SOL': 'solana',
    'ADA': 'cardano',
    'DOT': 'polkadot',
    'AVAX': 'avalanche-2',
    'MATIC': 'matic-network',
    'LINK': 'chainlink',
    'UNI': 'uniswap',
    'ATOM': 'cosmos',
    'XRP': 'ripple',
    'DOGE': 'dogecoin',
    'SHIB': 'shiba-inu',
    'PEPE': 'pepe',
    'LTC': 'litecoin',
    'BCH': 'bitcoin-cash',
    'XLM': 'stellar',
    'ALGO': 'algorand',
    'VET': 'vechain',
    'FIL': 'filecoin',
    'AAVE': 'aave',
    'XMR': 'monero',
    'ETC': 'ethereum-classic',
    'NEAR': 'near',
    'ARB': 'arbitrum',
    'OP': 'optimism',
}


class CoinGeckoService:
    """Service to fetch cryptocurrency data from CoinGecko"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_duration = timedelta(minutes=10)  # Longer cache to reduce API calls
        self._last_request = datetime.min
        self._rate_limit_delay = 3.0  # Increased delay for rate limiting
        self._max_retries = 3
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache_expiry:
            return False
        return datetime.now() < self._cache_expiry[key]
    
    async def _rate_limit(self):
        """Implement rate limiting for API calls"""
        elapsed = (datetime.now() - self._last_request).total_seconds()
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request = datetime.now()
    
    def _get_coingecko_id(self, ticker: str) -> str:
        """Convert ticker symbol to CoinGecko ID"""
        return CRYPTO_ID_MAP.get(ticker.upper(), ticker.lower())
    
    async def get_price(self, ticker: str, vs_currency: str = "usd") -> Optional[dict]:
        """Get current price for a cryptocurrency"""
        cache_key = f"{ticker}_{vs_currency}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        await self._rate_limit()
        
        coin_id = self._get_coingecko_id(ticker)
        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                if coin_id not in data:
                    return None
                
                coin_data = data[coin_id]
                price = coin_data.get(vs_currency, 0)
                change_24h = coin_data.get(f'{vs_currency}_24h_change', 0)
                
                result = {
                    'ticker': ticker.upper(),
                    'price': float(price),
                    'previous_close': float(price / (1 + change_24h / 100)) if change_24h else price,
                    'change': float(price * change_24h / 100) if change_24h else 0,
                    'change_percent': float(change_24h) if change_24h else 0,
                    'currency': vs_currency.upper(),
                    'market_cap': coin_data.get(f'{vs_currency}_market_cap', 0),
                    'volume_24h': coin_data.get(f'{vs_currency}_24h_vol', 0),
                    'name': ticker.upper(),
                    'last_updated': datetime.now().isoformat()
                }
                
                self._cache[cache_key] = result
                self._cache_expiry[cache_key] = datetime.now() + self._cache_duration
                
                return result
                
        except Exception as e:
            print(f"Error fetching {ticker} from CoinGecko: {e}")
            return None
    
    async def get_prices(self, tickers: List[str], vs_currency: str = "usd") -> Dict[str, dict]:
        """Get prices for multiple cryptocurrencies"""
        # Filter tickers that need fetching
        to_fetch = []
        results = {}
        
        for ticker in tickers:
            cache_key = f"{ticker}_{vs_currency}"
            if self._is_cache_valid(cache_key):
                results[ticker] = self._cache[cache_key]
            else:
                to_fetch.append(ticker)
        
        if not to_fetch:
            return results
        
        await self._rate_limit()
        
        # Batch request for efficiency
        coin_ids = [self._get_coingecko_id(t) for t in to_fetch]
        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true"
        }
        
        # Retry logic for rate limiting
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params, timeout=30.0)
                    
                    # Handle rate limiting
                    if response.status_code == 429:
                        wait_time = (attempt + 1) * 10  # 10, 20, 30 seconds
                        print(f"[WARN] CoinGecko rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    print(f"[DEBUG] CoinGecko response: {list(data.keys())}")
                    
                    for ticker, coin_id in zip(to_fetch, coin_ids):
                        if coin_id in data:
                            coin_data = data[coin_id]
                            price = coin_data.get(vs_currency, 0)
                            change_24h = coin_data.get(f'{vs_currency}_24h_change', 0)
                            
                            result = {
                                'ticker': ticker.upper(),
                                'price': float(price),
                                'previous_close': float(price / (1 + change_24h / 100)) if change_24h else price,
                                'change': float(price * change_24h / 100) if change_24h else 0,
                                'change_percent': float(change_24h) if change_24h else 0,
                                'currency': vs_currency.upper(),
                                'market_cap': coin_data.get(f'{vs_currency}_market_cap', 0),
                                'name': ticker.upper(),
                                'last_updated': datetime.now().isoformat()
                            }
                            
                            cache_key = f"{ticker}_{vs_currency}"
                            self._cache[cache_key] = result
                            self._cache_expiry[cache_key] = datetime.now() + self._cache_duration
                            results[ticker] = result
                            print(f"[DEBUG] Got price for {ticker}: {price} {vs_currency.upper()}")
                        else:
                            print(f"[WARN] No data for {ticker} (coin_id: {coin_id}) in response")
                    
                    break  # Success, exit retry loop
                            
            except Exception as e:
                print(f"[ERROR] Error fetching crypto prices (attempt {attempt + 1}): {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(5)  # Wait before retry
        
        print(f"[DEBUG] CoinGecko returning {len(results)} prices: {list(results.keys())}")
        return results
    
    async def get_history(self, ticker: str, days: int = 365, vs_currency: str = "usd") -> Optional[List[dict]]:
        """Get historical prices for a cryptocurrency"""
        # Check cache first
        cache_key = f"history_{ticker}_{days}_{vs_currency}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        await self._rate_limit()
        
        coin_id = self._get_coingecko_id(ticker)
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": vs_currency,
            "days": str(days),
            "interval": "daily" if days > 1 else "hourly"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=30.0)
                
                # Handle rate limiting
                if response.status_code == 429:
                    print(f"Rate limited by CoinGecko, waiting...")
                    await asyncio.sleep(60)  # Wait 1 minute
                    response = await client.get(url, params=params, timeout=30.0)
                
                response.raise_for_status()
                data = response.json()
                
                prices = data.get('prices', [])
                
                result = [
                    {
                        'date': datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d'),
                        'close': float(price),
                        'price': float(price)  # Alias for compatibility
                    }
                    for ts, price in prices
                ]
                
                # Cache for 30 minutes
                if result:
                    self._cache[cache_key] = result
                    self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=30)
                
                return result
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP error fetching history for {ticker}: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"Error fetching history for {ticker}: {e}")
            return None

