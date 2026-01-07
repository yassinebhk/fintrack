"""
Yahoo Finance Service
Fetches stock and ETF prices using Yahoo Finance API directly
Includes ticker mapping for problematic European ETFs
"""
import httpx
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Mapping for European ETFs that don't work with standard tickers
TICKER_MAPPING = {
    # Trade Republic / MyInvestor problematic tickers
    'LYX0F.DE': 'UST.PA',           # Amundi Nasdaq-100 -> Paris listing
    'IE00BYX5NX33': 'IE00BYX5NX33.SG',  # Fidelity MSCI World -> Stuttgart
    
    # Alternative mappings
    'SWDA.L': 'SWDA.L',             # iShares MSCI World (works)
    'VWCE.DE': 'VWCE.DE',           # Vanguard FTSE All-World
    'EUNL.DE': 'EUNL.DE',           # iShares MSCI World EUR
}

# Headers to mimic browser requests
YAHOO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}


class YahooFinanceService:
    """Service to fetch stock/ETF data from Yahoo Finance"""
    
    BASE_URL = "https://query1.finance.yahoo.com"
    
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
    
    def _get_mapped_ticker(self, ticker: str) -> str:
        """Get the correct Yahoo Finance ticker for problematic symbols"""
        return TICKER_MAPPING.get(ticker, ticker)
    
    async def _fetch_ticker_api(self, ticker: str) -> Optional[dict]:
        """Fetch ticker data directly from Yahoo Finance API"""
        mapped_ticker = self._get_mapped_ticker(ticker)
        url = f"{self.BASE_URL}/v8/finance/chart/{mapped_ticker}"
        
        params = {
            'interval': '1d',
            'range': '5d'
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=YAHOO_HEADERS, params=params)
                
                if response.status_code != 200:
                    print(f"[WARN] Yahoo API returned {response.status_code} for {ticker}")
                    return None
                
                data = response.json()
                
                result = data.get('chart', {}).get('result')
                if not result:
                    error = data.get('chart', {}).get('error', {})
                    print(f"[WARN] No data for {ticker} ({mapped_ticker}): {error.get('description', 'Unknown error')}")
                    return None
                
                meta = result[0].get('meta', {})
                
                current_price = meta.get('regularMarketPrice', 0)
                previous_close = meta.get('chartPreviousClose', current_price)
                currency = meta.get('currency', 'USD')
                
                # Convert USD to EUR for SGLD.L (listed in USD but we want EUR)
                if ticker == 'SGLD.L' and currency == 'USD':
                    # Approximate EUR conversion (you could fetch live rate)
                    usd_to_eur = 0.92
                    current_price = current_price * usd_to_eur
                    previous_close = previous_close * usd_to_eur
                    currency = 'EUR'
                
                print(f"[DEBUG] Yahoo API: {ticker} -> {mapped_ticker} = {current_price} {currency}")
                
                return {
                    'ticker': ticker,  # Return original ticker
                    'price': float(current_price),
                    'previous_close': float(previous_close),
                    'change': float(current_price - previous_close),
                    'change_percent': float((current_price - previous_close) / previous_close * 100) if previous_close else 0,
                    'currency': currency,
                    'name': meta.get('shortName', meta.get('longName', ticker)),
                    'market_cap': 0,
                    'last_updated': datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"[ERROR] Yahoo API error for {ticker}: {e}")
            return None
    
    def _fetch_ticker_yfinance(self, ticker: str) -> Optional[dict]:
        """Fallback: Synchronous fetch using yfinance library"""
        mapped_ticker = self._get_mapped_ticker(ticker)
        
        try:
            stock = yf.Ticker(mapped_ticker)
            info = stock.info
            hist = stock.history(period="1d")
            
            if hist.empty and not info.get('regularMarketPrice'):
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
            print(f"[ERROR] yfinance fallback error for {ticker}: {e}")
            return None
    
    async def get_price(self, ticker: str) -> Optional[dict]:
        """Get current price for a ticker"""
        if self._is_cache_valid(ticker):
            return self._cache[ticker]
        
        # Try API first
        result = await self._fetch_ticker_api(ticker)
        
        # Fallback to yfinance if API fails
        if not result:
            print(f"[INFO] Trying yfinance fallback for {ticker}")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, 
                self._fetch_ticker_yfinance, 
                ticker
            )
        
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
    
    async def _fetch_history_api(self, ticker: str, period: str = "1y") -> Optional[List[dict]]:
        """Fetch historical data from Yahoo Finance API"""
        mapped_ticker = self._get_mapped_ticker(ticker)
        url = f"{self.BASE_URL}/v8/finance/chart/{mapped_ticker}"
        
        # Map period to Yahoo format
        period_map = {
            '1m': '1mo',
            '3m': '3mo', 
            '6m': '6mo',
            '1y': '1y',
            '5y': '5y',
            'max': 'max'
        }
        yahoo_period = period_map.get(period, '1y')
        
        params = {
            'interval': '1d',
            'range': yahoo_period
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=YAHOO_HEADERS, params=params)
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                result = data.get('chart', {}).get('result')
                
                if not result:
                    return None
                
                timestamps = result[0].get('timestamp', [])
                quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
                
                history = []
                for i, ts in enumerate(timestamps):
                    try:
                        close = quotes.get('close', [])[i]
                        if close is not None:
                            history.append({
                                'date': datetime.fromtimestamp(ts).strftime('%Y-%m-%d'),
                                'open': quotes.get('open', [])[i] or close,
                                'high': quotes.get('high', [])[i] or close,
                                'low': quotes.get('low', [])[i] or close,
                                'close': close,
                                'volume': quotes.get('volume', [])[i] or 0
                            })
                    except (IndexError, TypeError):
                        continue
                
                return history if history else None
                
        except Exception as e:
            print(f"[ERROR] Yahoo API history error for {ticker}: {e}")
            return None
    
    def _fetch_history_yfinance(self, ticker: str, period: str = "1y") -> Optional[List[dict]]:
        """Fallback: Fetch historical data using yfinance"""
        mapped_ticker = self._get_mapped_ticker(ticker)
        
        try:
            stock = yf.Ticker(mapped_ticker)
            hist = stock.history(period=period, timeout=30)
            
            if hist.empty:
                return None
            
            result = []
            for date, row in hist.iterrows():
                close_val = float(row['Close']) if 'Close' in row else 0
                if close_val > 0:
                    result.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'open': float(row.get('Open', close_val)),
                        'high': float(row.get('High', close_val)),
                        'low': float(row.get('Low', close_val)),
                        'close': close_val,
                        'volume': int(row.get('Volume', 0))
                    })
            
            return result if result else None
            
        except Exception as e:
            print(f"[ERROR] yfinance history fallback error for {ticker}: {e}")
            return None
    
    async def get_history(self, ticker: str, period: str = "1y") -> Optional[List[dict]]:
        """Get historical prices for a ticker"""
        cache_key = f"history_{ticker}_{period}"
        
        if cache_key in self._cache_expiry and datetime.now() < self._cache_expiry[cache_key]:
            return self._cache.get(cache_key)
        
        # Try API first
        result = await self._fetch_history_api(ticker, period)
        
        # Fallback to yfinance
        if not result:
            print(f"[INFO] Trying yfinance history fallback for {ticker}")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_history_yfinance,
                ticker,
                period
            )
        
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
