"""Web search via keyless news RSS — real, current news headlines, NO API key.

Two independent, keyless, free sources so one being throttled doesn't zero out
coverage: Google News RSS (primary, has a `when:Nd` recency operator) with a
fallback to Bing News RSS (different host — survives a Google rate-flag). Graceful
by design: if both fail, search() returns [] and the caller simply produces no
brief — nothing else breaks.

Each result is {title, url, content}; the headline itself is the substance (the
LLM is told to use ONLY what's here), annotated with publisher/snippet + date.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import httpx
from loguru import logger
from xml.etree import ElementTree as ET

_GNEWS_URL = "https://news.google.com/rss/search"
_BING_URL = "https://www.bing.com/news/search"
_UA = "Mozilla/5.0 (compatible; FinTrack/1.0; +https://personalfintrack.duckdns.org)"
_TAG_RE = re.compile(r"<[^>]+>")


def enabled() -> bool:
    # No API key needed — both sources are keyless and free.
    return True


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()


async def _fetch_xml(url: str, label: str, query: str) -> ET.Element | None:
    """GET an RSS URL and parse it, retrying transient/throttled responses."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": _UA},
                                         follow_redirects=True) as client:
                r = await client.get(url)
            if r.status_code == 200:
                return ET.fromstring(r.content)
            logger.warning("{} search {} -> HTTP {} (attempt {})", label, query[:50], r.status_code, attempt + 1)
        except Exception as exc:
            logger.warning("{} search error for {} (attempt {}): {}", label, query[:50], attempt + 1, exc)
        if attempt < 2:
            await asyncio.sleep(2.0 * (attempt + 1))
    return None


_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


async def _search_gnews(query: str, max_results: int, days: int) -> list[dict]:
    q = f"{query} when:{max(int(days), 1)}d"
    params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    root = await _fetch_xml(f"{_GNEWS_URL}?{urllib.parse.urlencode(params)}", "gnews", query)
    if root is None:
        return []
    out: list[dict] = []
    for item in root.findall(".//item"):
        title = _clean(item.findtext("title"))
        if not title:
            continue
        link = (item.findtext("link") or "").strip()
        src_el = item.find("source")
        publisher = _clean(src_el.text) if src_el is not None else ""
        when = ""
        parsed_dt = None
        pub = item.findtext("pubDate")
        if pub:
            try:
                parsed_dt = parsedate_to_datetime(pub)
                when = parsed_dt.date().isoformat()
            except Exception:
                pass
        # The headline carries the substance; annotate with publisher + date so
        # the LLM can weigh recency and cite the source.
        content = " · ".join(x for x in [publisher, when] if x)
        out.append({"title": title, "url": link, "content": content, "_dt": parsed_dt})
        # NOTE: no early break here on purpose — see the sort below.
    # Google ranks these by RELEVANCE, not recency. Within the `when:Nd` window a
    # high-volume old story (e.g. an earnings miss) can out-rank a quieter but
    # more decision-relevant recent one (e.g. an index-inclusion announcement) —
    # confirmed live: a brief generated weeks after a Sept 4 S&P 500 addition
    # announcement was still citing only early-August headlines. Re-sort
    # newest-first before truncating so the freshest items always survive the cut.
    out.sort(key=lambda r: r["_dt"] or _MIN_DT, reverse=True)
    for r in out:
        r.pop("_dt", None)
    return out[:max_results]


async def _search_bing(query: str, max_results: int, days: int) -> list[dict]:
    """Fallback source (different host from Google). Bing News RSS has no recency
    operator, so we filter by pubDate client-side (keeping undated items)."""
    params = {"q": query, "format": "rss"}
    root = await _fetch_xml(f"{_BING_URL}?{urllib.parse.urlencode(params)}", "bing", query)
    if root is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(int(days), 1))
    out: list[dict] = []
    for item in root.findall(".//item"):
        title = _clean(item.findtext("title"))
        if not title:
            continue
        link = (item.findtext("link") or "").strip()
        when = ""
        parsed_dt = None
        pub = item.findtext("pubDate")
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
                when = dt.date().isoformat()
                parsed_dt = dt
            except Exception:
                pass
        desc = _clean(item.findtext("description"))[:200]
        content = " · ".join(x for x in [desc, when] if x)
        out.append({"title": title, "url": link, "content": content, "_dt": parsed_dt})
        # Same relevance-vs-recency issue as Google News — sort before truncating.
    out.sort(key=lambda r: r["_dt"] or _MIN_DT, reverse=True)
    for r in out:
        r.pop("_dt", None)
    return out[:max_results]


async def search(query: str, max_results: int = 8, days: int = 30) -> list[dict]:
    """Return recent news [{title, url, content}] for `query`, or [] on failure.
    Google News first (recency-filtered); Bing News as fallback when Google is
    empty/throttled, so a rate-flag on one host doesn't kill coverage."""
    results = await _search_gnews(query, max_results, days)
    if results:
        return results
    return await _search_bing(query, max_results, days)
