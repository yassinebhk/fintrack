"""Web search via Google News RSS — real, current news headlines, NO API key.

Keyless and free: Google News exposes a public RSS search endpoint, so there's
no third-party signup or key to manage. Graceful by design: on any error search()
returns [] and the caller simply produces no brief — nothing else breaks.

We use the `when:Nd` query operator so the results are both recent and sorted by
date. Each result is {title, url, content}; the headline itself is the substance
(the LLM is told to use ONLY what's here), annotated with publisher + date.
"""

from __future__ import annotations

import re
import urllib.parse
from email.utils import parsedate_to_datetime

import httpx
from loguru import logger
from xml.etree import ElementTree as ET

_GNEWS_URL = "https://news.google.com/rss/search"
_UA = "Mozilla/5.0 (compatible; FinTrack/1.0; +https://personalfintrack.duckdns.org)"
_TAG_RE = re.compile(r"<[^>]+>")


def enabled() -> bool:
    # No API key needed — Google News RSS is keyless and free.
    return True


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()


async def search(query: str, max_results: int = 8, days: int = 30) -> list[dict]:
    """Return recent news [{title, url, content}] for `query` from Google News
    RSS, or [] on any failure. `days` restricts to the last N days (server-side
    via the `when:` operator, so results come back recent and date-sorted)."""
    q = f"{query} when:{max(int(days), 1)}d"
    params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = f"{_GNEWS_URL}?{urllib.parse.urlencode(params)}"
    try:
        async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": _UA},
                                     follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.warning("gnews search {} -> HTTP {}", query[:50], r.status_code)
                return []
            root = ET.fromstring(r.content)
    except Exception as exc:
        logger.warning("gnews search error for {}: {}", query[:50], exc)
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
        pub = item.findtext("pubDate")
        if pub:
            try:
                when = parsedate_to_datetime(pub).date().isoformat()
            except Exception:
                pass
        # The headline carries the substance; annotate with publisher + date so
        # the LLM can weigh recency and cite the source.
        content = " · ".join(x for x in [publisher, when] if x)
        out.append({"title": title, "url": link, "content": content})
        if len(out) >= max_results:
            break
    return out
