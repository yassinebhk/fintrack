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
            
            # Try with different methods
            hist = None
            
            # Method 1: Direct history call
            try:
                hist = stock.history(period=period, timeout=30)
            except Exception as e1:
                print(f"Method 1 failed for {ticker}: {e1}")
            
            # Method 2: Try with auto_adjust=False
            if hist is None or hist.empty:
                try:
                    hist = stock.history(period=period, auto_adjust=False, timeout=30)
                except Exception as e2:
                    print(f"Method 2 failed for {ticker}: {e2}")
            
            # Method 3: Try downloading directly
            if hist is None or hist.empty:
                try:
                    import yfinance as yf_direct
                    hist = yf_direct.download(ticker, period=period, progress=False, timeout=30)
                except Exception as e3:
                    print(f"Method 3 failed for {ticker}: {e3}")
            
            if hist is None or hist.empty:
                print(f"No data found for {ticker} after all methods")
                return None
            
            # Handle both single and multi-level column names
            close_col = 'Close' if 'Close' in hist.columns else ('Close', ticker) if ('Close', ticker) in hist.columns else None
            open_col = 'Open' if 'Open' in hist.columns else ('Open', ticker) if ('Open', ticker) in hist.columns else None
            high_col = 'High' if 'High' in hist.columns else ('High', ticker) if ('High', ticker) in hist.columns else None
            low_col = 'Low' if 'Low' in hist.columns else ('Low', ticker) if ('Low', ticker) in hist.columns else None
            vol_col = 'Volume' if 'Volume' in hist.columns else ('Volume', ticker) if ('Volume', ticker) in hist.columns else None
            
            result = []
            for date, row in hist.iterrows():
                try:
                    close_val = float(row[close_col]) if close_col and close_col in row else 0
                    open_val = float(row[open_col]) if open_col and open_col in row else close_val
                    high_val = float(row[high_col]) if high_col and high_col in row else close_val
                    low_val = float(row[low_col]) if low_col and low_col in row else close_val
                    vol_val = int(row[vol_col]) if vol_col and vol_col in row else 0
                    
                    if close_val > 0:  # Only add valid data points
                        result.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'open': open_val,
                            'high': high_val,
                            'low': low_val,
                            'close': close_val,
                            'volume': vol_val
                        })
                except Exception as row_err:
                    print(f"Error processing row for {ticker}: {row_err}")
                    continue
            
            return result if result else None
            
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

