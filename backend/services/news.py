"""
News Service
Fetches real financial news from RSS feeds (free, no API key required)
"""
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
import re
import html


# RSS Feed sources for financial news
RSS_FEEDS = {
    'stocks': [
        {
            'url': 'https://feeds.bloomberg.com/markets/news.rss',
            'source': 'Bloomberg',
            'category': 'stocks'
        },
        {
            'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
            'source': 'CNBC',
            'category': 'stocks'
        },
        {
            'url': 'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US',
            'source': 'Yahoo Finance',
            'category': 'stocks'
        },
    ],
    'crypto': [
        {
            'url': 'https://cointelegraph.com/rss',
            'source': 'Cointelegraph',
            'category': 'crypto'
        },
        {
            'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'source': 'CoinDesk',
            'category': 'crypto'
        },
    ],
    'economy': [
        {
            'url': 'https://feeds.reuters.com/reuters/businessNews',
            'source': 'Reuters',
            'category': 'economy'
        },
        {
            'url': 'https://www.ft.com/rss/home',
            'source': 'Financial Times',
            'category': 'economy'
        },
    ],
    'politics': [
        {
            'url': 'https://feeds.reuters.com/Reuters/worldNews',
            'source': 'Reuters World',
            'category': 'politics'
        },
    ],
    'spain': [
        {
            'url': 'https://e00-expansion.uecdn.es/rss/mercados.xml',
            'source': 'Expansión',
            'category': 'economy'
        },
        {
            'url': 'https://www.eleconomista.es/rss/rss-mercados.php',
            'source': 'El Economista',
            'category': 'stocks'
        },
    ]
}

# Keywords to detect market impact
BULLISH_KEYWORDS = ['surge', 'soar', 'rally', 'gain', 'rise', 'jump', 'record high', 'bullish', 'sube', 'gana', 'récord', 'máximo']
BEARISH_KEYWORDS = ['crash', 'plunge', 'fall', 'drop', 'decline', 'tumble', 'bearish', 'crisis', 'cae', 'pierde', 'baja', 'desplome']

# Asset ticker detection patterns
ASSET_PATTERNS = {
    'BTC': r'\b(bitcoin|btc)\b',
    'ETH': r'\b(ethereum|eth)\b',
    'SOL': r'\b(solana|sol)\b',
    'DOGE': r'\b(dogecoin|doge)\b',
    'PEPE': r'\b(pepe)\b',
    'AAPL': r'\b(apple|aapl)\b',
    'MSFT': r'\b(microsoft|msft)\b',
    'GOOGL': r'\b(google|alphabet|googl)\b',
    'AMZN': r'\b(amazon|amzn)\b',
    'TSLA': r'\b(tesla|tsla)\b',
    'NVDA': r'\b(nvidia|nvda)\b',
    'META': r'\b(meta|facebook)\b',
    'SPY': r'\b(s&p 500|s&p500|spy)\b',
    'QQQ': r'\b(nasdaq|qqq)\b',
    'GOLD': r'\b(gold|oro)\b',
    'OIL': r'\b(oil|petróleo|petroleum|crude)\b',
}


class NewsService:
    """Service to fetch and process financial news from RSS feeds"""
    
    def __init__(self):
        self._cache: List[Dict] = []
        self._cache_expiry: datetime = datetime.min
        self._cache_duration = timedelta(minutes=30)  # Cache news for 30 minutes
    
    def _is_cache_valid(self) -> bool:
        """Check if cached news is still valid"""
        return datetime.now() < self._cache_expiry and len(self._cache) > 0
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and decode entities"""
        if not text:
            return ""
        # Decode HTML entities
        text = html.unescape(text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text[:500]  # Limit length
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various RSS date formats"""
        if not date_str:
            return datetime.now()
        
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
            '%d %b %Y %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return datetime.now()
    
    def _detect_impact(self, title: str, description: str) -> str:
        """Detect market impact from news text"""
        text = f"{title} {description}".lower()
        
        bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
        
        if bullish_count > bearish_count:
            return 'bullish'
        elif bearish_count > bullish_count:
            return 'bearish'
        return 'neutral'
    
    def _detect_assets(self, title: str, description: str) -> List[str]:
        """Detect mentioned assets from news text"""
        text = f"{title} {description}".lower()
        assets = []
        
        for ticker, pattern in ASSET_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                assets.append(ticker)
        
        return assets[:5]  # Limit to 5 assets
    
    async def _fetch_feed(self, feed_info: Dict) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        news_items = []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    feed_info['url'],
                    timeout=10.0,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; FinTrack/1.0)'
                    },
                    follow_redirects=True
                )
                
                if response.status_code != 200:
                    print(f"Failed to fetch {feed_info['source']}: {response.status_code}")
                    return []
                
                # Parse XML
                root = ET.fromstring(response.content)
                
                # Find items (RSS 2.0 or Atom format)
                items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
                
                for item in items[:10]:  # Limit to 10 items per feed
                    # RSS 2.0 format
                    title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or ''
                    link = item.findtext('link') or ''
                    if not link:
                        link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                        if link_elem is not None:
                            link = link_elem.get('href', '')
                    
                    description = item.findtext('description') or item.findtext('{http://www.w3.org/2005/Atom}summary') or ''
                    pub_date = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or ''
                    
                    if not title:
                        continue
                    
                    title_clean = self._clean_html(title)
                    description_clean = self._clean_html(description)
                    
                    news_item = {
                        'title': title_clean,
                        'excerpt': description_clean[:300] + '...' if len(description_clean) > 300 else description_clean,
                        'source': feed_info['source'],
                        'category': feed_info['category'],
                        'url': link,
                        'date': self._parse_date(pub_date).strftime('%Y-%m-%d'),
                        'datetime': self._parse_date(pub_date).isoformat(),
                        'impact': self._detect_impact(title_clean, description_clean),
                        'impactedAssets': self._detect_assets(title_clean, description_clean),
                    }
                    
                    news_items.append(news_item)
                    
        except ET.ParseError as e:
            print(f"XML parse error for {feed_info['source']}: {e}")
        except Exception as e:
            print(f"Error fetching {feed_info['source']}: {e}")
        
        return news_items
    
    async def get_news(self, category: str = 'all', limit: int = 30) -> List[Dict]:
        """Get news from all sources or filtered by category"""
        
        # Check cache first
        if self._is_cache_valid():
            cached = self._cache
            if category != 'all':
                cached = [n for n in cached if n['category'] == category]
            return cached[:limit]
        
        # Fetch from all feeds
        all_feeds = []
        
        if category == 'all':
            for cat_feeds in RSS_FEEDS.values():
                all_feeds.extend(cat_feeds)
        elif category in RSS_FEEDS:
            all_feeds = RSS_FEEDS[category]
        else:
            # Unknown category, return empty
            return []
        
        # Fetch feeds concurrently
        tasks = [self._fetch_feed(feed) for feed in all_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine and sort news
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
        
        # Remove duplicates by title similarity
        seen_titles = set()
        unique_news = []
        for news in all_news:
            title_key = news['title'][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(news)
        
        # Sort by date (newest first)
        unique_news.sort(key=lambda x: x['datetime'], reverse=True)
        
        # Update cache
        self._cache = unique_news
        self._cache_expiry = datetime.now() + self._cache_duration
        
        # Filter by category if needed
        if category != 'all':
            unique_news = [n for n in unique_news if n['category'] == category]
        
        return unique_news[:limit]
    
    async def get_news_for_asset(self, ticker: str, limit: int = 10) -> List[Dict]:
        """Get news related to a specific asset"""
        all_news = await self.get_news('all', 100)
        
        # Filter news that mention the ticker
        ticker_upper = ticker.upper()
        related_news = [
            n for n in all_news 
            if ticker_upper in n.get('impactedAssets', []) or 
               ticker_upper.lower() in n['title'].lower() or
               ticker_upper.lower() in n['excerpt'].lower()
        ]
        
        return related_news[:limit]

