"""
Yahoo Finance Service
Fetches stock and ETF prices using yfinance library (free, no API key)
"""
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor


class YahooFinanceService:
    """Service to fetch stock/ETF data from Yahoo Finance"""
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._cache: Dict[str, dict] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_duration = timedelta(minutes=15)
    
    def _is_cache_valid(self, ticker: str) -> bool:
        """Check if cached data is still valid"""
        if ticker not in self._cache_expiry:
            return False
        return datetime.now() < self._cache_expiry[ticker]
    
    def _fetch_ticker_sync(self, ticker: str) -> Optional[dict]:
        """Synchronous fetch of ticker data"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1d")
            
            if hist.empty:
                return None
            
            current_price = hist['Close'].iloc[-1] if not hist.empty else info.get('regularMarketPrice', 0)
            previous_close = info.get('previousClose', current_price)
            
            return {
                'ticker': ticker,
                'price': float(current_price),
                'previous_close': float(previous_close),
                'change': float(current_price - previous_close),
                'change_percent': float((current_price - previous_close) / previous_close * 100) if previous_close else 0,
                'currency': info.get('currency', 'USD'),
                'name': info.get('shortName', ticker),
                'market_cap': info.get('marketCap', 0),
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    async def get_price(self, ticker: str) -> Optional[dict]:
        """Get current price for a ticker"""
        if self._is_cache_valid(ticker):
            return self._cache[ticker]
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._fetch_ticker_sync, ticker)
        
        if result:
            self._cache[ticker] = result
            self._cache_expiry[ticker] = datetime.now() + self._cache_duration
        
        return result
    
    async def get_prices(self, tickers: List[str]) -> Dict[str, dict]:
        """Get prices for multiple tickers concurrently"""
        tasks = [self.get_price(ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        
        return {
            ticker: result 
            for ticker, result in zip(tickers, results) 
            if result is not None
        }
    
    def _fetch_history_sync(self, ticker: str, period: str = "1y") -> Optional[List[dict]]:
        """Fetch historical data synchronously"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                return None
            
            return [
                {
                    'date': date.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                }
                for date, row in hist.iterrows()
            ]
        except Exception as e:
            print(f"Error fetching history for {ticker}: {e}")
            return None
    
    async def get_history(self, ticker: str, period: str = "1y") -> Optional[List[dict]]:
        """Get historical prices for a ticker"""
        # Check cache first
        cache_key = f"history_{ticker}_{period}"
        if cache_key in self._cache_expiry and datetime.now() < self._cache_expiry[cache_key]:
            return self._cache.get(cache_key)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, 
            self._fetch_history_sync, 
            ticker, 
            period
        )
        
        # Cache for 30 minutes
        if result:
            self._cache[cache_key] = result
            self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=30)
        
        return result
    
    async def get_multiple_history(self, tickers: List[str], period: str = "1y") -> Dict[str, List[dict]]:
        """Get historical data for multiple tickers"""
        tasks = [self.get_history(ticker, period) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        
        return {
            ticker: result
            for ticker, result in zip(tickers, results)
            if result is not None
        }

