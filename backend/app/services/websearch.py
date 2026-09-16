"""Web search via Tavily — real, current web results for catalyst/environment briefs.

Graceful by design: if no TAVILY_API_KEY is set (or Tavily is unreachable), search()
returns [] and the caller simply produces no brief — nothing else breaks.
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import get_settings

_TAVILY_URL = "https://api.tavily.com/search"


def enabled() -> bool:
    return bool(get_settings().tavily_api_key)


async def search(query: str, max_results: int = 6, days: int = 30) -> list[dict]:
    """Return recent web results [{title, url, content}] for `query`, or [] if
    web search isn't configured / fails. `days` limits to recent news."""
    key = get_settings().tavily_api_key
    if not key:
        return []
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "topic": "news",
        "days": days,
        "max_results": max_results,
        "include_answer": False,
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.post(_TAVILY_URL, json=payload)
            if r.status_code != 200:
                logger.warning("tavily search {} -> HTTP {}", query[:50], r.status_code)
                return []
            data = r.json()
    except Exception as exc:
        logger.warning("tavily search error for {}: {}", query[:50], exc)
        return []
    out = []
    for it in (data.get("results") or []):
        out.append({
            "title": it.get("title") or "",
            "url": it.get("url") or "",
            "content": (it.get("content") or "")[:600],
        })
    return out
