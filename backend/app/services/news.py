"""News aggregation from financial RSS feeds with basic impact / asset detection.

Loguru replaces prints; same public API as legacy.
"""

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import httpx
from loguru import logger


RSS_FEEDS = {
    "stocks": [
        {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg", "category": "stocks"},
        {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC", "category": "stocks"},
        {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "source": "Yahoo Finance", "category": "stocks"},
    ],
    "crypto": [
        {"url": "https://cointelegraph.com/rss", "source": "Cointelegraph", "category": "crypto"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk", "category": "crypto"},
    ],
    "economy": [
        {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters", "category": "economy"},
        {"url": "https://www.ft.com/rss/home", "source": "Financial Times", "category": "economy"},
    ],
    "politics": [
        {"url": "https://feeds.reuters.com/Reuters/worldNews", "source": "Reuters World", "category": "politics"},
    ],
    "spain": [
        {"url": "https://e00-expansion.uecdn.es/rss/mercados.xml", "source": "Expansión", "category": "economy"},
        {"url": "https://www.eleconomista.es/rss/rss-mercados.php", "source": "El Economista", "category": "stocks"},
    ],
}

BULLISH_KEYWORDS = ["surge", "soar", "rally", "gain", "rise", "jump", "record high", "bullish", "sube", "gana", "récord", "máximo"]
BEARISH_KEYWORDS = ["crash", "plunge", "fall", "drop", "decline", "tumble", "bearish", "crisis", "cae", "pierde", "baja", "desplome"]

ASSET_PATTERNS = {
    "BTC": r"\b(bitcoin|btc)\b",
    "ETH": r"\b(ethereum|eth)\b",
    "SOL": r"\b(solana|sol)\b",
    "DOGE": r"\b(dogecoin|doge)\b",
    "PEPE": r"\b(pepe)\b",
    "AAPL": r"\b(apple|aapl)\b",
    "MSFT": r"\b(microsoft|msft)\b",
    "GOOGL": r"\b(google|alphabet|googl)\b",
    "AMZN": r"\b(amazon|amzn)\b",
    "TSLA": r"\b(tesla|tsla)\b",
    "NVDA": r"\b(nvidia|nvda)\b",
    "META": r"\b(meta|facebook)\b",
    "SPY": r"\b(s&p 500|s&p500|spy)\b",
    "QQQ": r"\b(nasdaq|qqq)\b",
    "GOLD": r"\b(gold|oro)\b",
    "OIL": r"\b(oil|petróleo|petroleum|crude)\b",
    "PLTR": r"\b(palantir|pltr)\b",
    "SPCX": r"\b(spacex|space x)\b",
}


class NewsService:
    def __init__(self, cache_ttl: timedelta = timedelta(minutes=30)) -> None:
        self._cache: list[dict] = []
        self._expiry = datetime.min
        self._ttl = cache_ttl

    def _fresh(self) -> bool:
        return datetime.now() < self._expiry and bool(self._cache)

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = " ".join(text.split())
        return text[:500]

    def _parse_date(self, raw: str) -> datetime:
        if not raw:
            return datetime.now()
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        return datetime.now()

    def _impact(self, title: str, desc: str) -> str:
        text = f"{title} {desc}".lower()
        b = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        x = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
        if b > x:
            return "bullish"
        if x > b:
            return "bearish"
        return "neutral"

    def _detect_assets(self, title: str, desc: str) -> list[str]:
        text = f"{title} {desc}".lower()
        return [t for t, pat in ASSET_PATTERNS.items() if re.search(pat, text, re.IGNORECASE)][:5]

    async def _fetch_feed(self, feed: dict) -> list[dict]:
        items_out: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    feed["url"],
                    headers={"User-Agent": "Mozilla/5.0 (compatible; FinTrack/2.0)"},
                )
                if resp.status_code != 200:
                    logger.warning("rss {} -> HTTP {}", feed["source"], resp.status_code)
                    return []
                root = ET.fromstring(resp.content)
                items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                for item in items[:10]:
                    title = (
                        item.findtext("title")
                        or item.findtext("{http://www.w3.org/2005/Atom}title")
                        or ""
                    )
                    link = item.findtext("link") or ""
                    if not link:
                        link_el = item.find("{http://www.w3.org/2005/Atom}link")
                        if link_el is not None:
                            link = link_el.get("href", "")
                    desc = (
                        item.findtext("description")
                        or item.findtext("{http://www.w3.org/2005/Atom}summary")
                        or ""
                    )
                    pub = item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}published") or ""
                    if not title:
                        continue
                    title_c = self._clean(title)
                    desc_c = self._clean(desc)
                    items_out.append({
                        "title": title_c,
                        "excerpt": (desc_c[:300] + "...") if len(desc_c) > 300 else desc_c,
                        "source": feed["source"],
                        "category": feed["category"],
                        "url": link,
                        "date": self._parse_date(pub).strftime("%Y-%m-%d"),
                        "datetime": self._parse_date(pub).isoformat(),
                        "impact": self._impact(title_c, desc_c),
                        "impactedAssets": self._detect_assets(title_c, desc_c),
                    })
        except ET.ParseError as exc:
            logger.warning("rss xml parse error in {}: {}", feed["source"], exc)
        except Exception as exc:
            logger.error("rss fetch error in {}: {}", feed["source"], exc)
        return items_out

    async def get_news(self, category: str = "all", limit: int = 30) -> list[dict]:
        if self._fresh():
            data = self._cache
            if category != "all":
                data = [n for n in data if n["category"] == category]
            return data[:limit]

        if category == "all":
            feeds = [f for group in RSS_FEEDS.values() for f in group]
        elif category in RSS_FEEDS:
            feeds = RSS_FEEDS[category]
        else:
            return []

        results = await asyncio.gather(*(self._fetch_feed(f) for f in feeds), return_exceptions=True)
        all_news: list[dict] = []
        for r in results:
            if isinstance(r, list):
                all_news.extend(r)

        seen = set()
        unique = []
        for n in all_news:
            key = n["title"][:50].lower()
            if key not in seen:
                seen.add(key)
                unique.append(n)
        unique.sort(key=lambda x: x["datetime"], reverse=True)

        # Upgrade sentiment from keyword-heuristic to LLM classification (batch, cached)
        await self._classify_sentiment_llm(unique[:40])

        self._cache = unique
        self._expiry = datetime.now() + self._ttl

        if category != "all":
            unique = [n for n in unique if n["category"] == category]
        return unique[:limit]

    async def _classify_sentiment_llm(self, items: list[dict]) -> None:
        """Re-classify market sentiment of headlines with the LLM (1 batch call).

        Falls back silently to the keyword heuristic already set on each item.
        """
        if not items:
            return
        from app.config import get_settings

        settings = get_settings()
        if not settings.has_gemini and not settings.has_groq:
            return

        try:
            from app.llm import LLMMessage, get_llm_client

            numbered = "\n".join(f"{i}. {it['title']}" for i, it in enumerate(items))
            schema = {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "i": {"type": "integer"},
                                "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                            },
                            "required": ["i", "sentiment"],
                        },
                    }
                },
                "required": ["items"],
            }
            client = get_llm_client()
            resp = await client.generate(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "Eres un analista de mercados. Clasifica el sentimiento de mercado de cada "
                            "titular como bullish (alcista, buenas noticias para los precios), bearish "
                            "(bajista) o neutral. Juzga el titular COMPLETO, no palabras sueltas: "
                            "'mayor compra de Ethereum' o 'predice supercycle' es bullish, no bearish."
                        ),
                    ),
                    LLMMessage(role="user", content=f"Titulares:\n{numbered}\n\nDevuelve JSON con items[].i e items[].sentiment."),
                ],
                model=settings.gemini_model_cheap,
                max_tokens=2048,
                temperature=0.0,
                json_schema=schema,
            )
            data = resp.structured or {}
            for entry in data.get("items", []):
                idx = entry.get("i")
                sent = entry.get("sentiment")
                if isinstance(idx, int) and 0 <= idx < len(items) and sent in ("bullish", "bearish", "neutral"):
                    items[idx]["impact"] = sent
            logger.info("news sentiment re-classified by LLM ({} items)", len(data.get("items", [])))
        except Exception as exc:
            logger.warning("LLM sentiment classification failed, keeping keyword heuristic: {}", exc)

    async def get_news_for_asset(self, ticker: str, limit: int = 10) -> list[dict]:
        all_news = await self.get_news("all", 100)
        upper = ticker.upper()
        related = [
            n for n in all_news
            if upper in n.get("impactedAssets", [])
            or upper.lower() in n["title"].lower()
            or upper.lower() in n["excerpt"].lower()
        ]
        return related[:limit]
