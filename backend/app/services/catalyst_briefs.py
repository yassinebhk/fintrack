"""Catalyst / environment briefs — the 'what's the fundamental context' layer the
momentum engine lacks. For a held or recommended asset we pull real, recent news
(Google News RSS — keyless) and have the LLM synthesize a short, SOURCED brief:
recent catalysts, environment risks (competition, sector, regulation) and a
one-line verdict.

Grounded on REAL headlines — if the news search returns nothing, NO brief is
produced (we never fabricate a brief from stale model memory). Cached per ticker
for a few days so we don't hammer the feed.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from loguru import logger

from app.llm import LLMMessage, get_llm_client
from app.services import websearch

_KEY = "catalyst_briefs"
_TTL_DAYS = 3
_MAX_PER_RUN = 30   # cap per batch so we never hammer the news feed

# Fund/ETF boilerplate that only narrows a news search (an ETF's news is about
# its geography/theme, e.g. "Franklin FTSE Taiwan", not the "UCITS ETF" suffix).
_FUND_STOP = {
    "ucits", "uci", "etf", "etn", "etc", "fund", "index", "acc", "accumulating",
    "dist", "distributing", "hedged", "swap", "core", "select", "sector",
    "eur", "usd", "gbp", "chf", "plc", "1c", "1d",
}


def _clean_name(name: str) -> str:
    """Strip fund/share-class boilerplate so the geographic/thematic words drive
    the news search. 'Franklin FTSE Taiwan UCITS ETF' -> 'Franklin FTSE Taiwan'."""
    n = re.sub(r"\([^)]*\)", " ", name or "")
    toks = [t for t in re.split(r"[\s\-–—]+", n) if t]
    kept = [t for t in toks if t.lower().strip(".") not in _FUND_STOP]
    return " ".join(kept).strip() or (name or "").strip()


_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _is_weak_name(name: str, ticker: str) -> bool:
    """A name is 'weak' (useless for a news search) if it's empty, equals the
    ticker, or is a bare symbol/ISIN/code (e.g. 'NUKL.DE', 'IE00BYX5NX33')."""
    n = (name or "").strip()
    if not n or n.upper() == (ticker or "").upper():
        return True
    if ".." in n:  # truncated/garbled exchange name, e.g. 'SSSPDR S+P US Ut..Sel.Se.U'
        return True
    toks = n.lower().split()
    if "plc" in toks or "iii" in toks:  # umbrella-fund cruft, e.g. 'ISHARES III PLC ISH CORE E'
        return True
    if " " not in n:
        u = n.upper()
        if _ISIN_RE.match(u) or u.startswith("0P") or "." in u:
            return True
    return False


def _yf_name_sync(ticker: str) -> str:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return (info.get("longName") or info.get("shortName") or "").strip()
    except Exception:
        return ""


async def _resolve_name(ticker: str, name: str) -> str:
    """When the stored name is just the ticker/ISIN, look up a real human name so
    the news search has something to match. Yahoo's longName is clean ('VanEck
    Uranium and Nuclear Technologies UCITS ETF'); fall back to its quote name."""
    if not _is_weak_name(name, ticker):
        return name
    better = await asyncio.to_thread(_yf_name_sync, ticker)
    if not better:
        try:
            from app.services.market.yahoo_finance import YahooFinanceService
            d = await YahooFinanceService().get_price(ticker)
            better = ((d or {}).get("name") or "").strip()
        except Exception:
            better = ""
    if better and " " in better and not _is_weak_name(better, ticker):
        return better
    return name


async def _load() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        return (row.payload or {}).get("items", {}) if row and row.payload else {}
    except Exception as exc:
        logger.warning("catalyst_briefs load failed: {}", exc)
        return {}


async def _save(items: dict) -> None:
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    payload = {"items": items}
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


async def get_brief(ticker: str) -> dict | None:
    return (await _load()).get((ticker or "").upper())


def _fresh(brief: dict) -> bool:
    try:
        gen = datetime.fromisoformat(brief.get("generated_at"))
        return (datetime.now(timezone.utc) - gen).days < _TTL_DAYS
    except Exception:
        return False


async def generate_brief(ticker: str, name: str = "") -> dict | None:
    """Search the web + synthesize a sourced catalyst/environment brief. Returns
    None if web search is unavailable or found nothing relevant."""
    if not websearch.enabled():
        return None
    # Resolve a real name when the stored one is just the ticker/ISIN, otherwise
    # the search has nothing to match (e.g. 'NUKL.DE' -> 'VanEck Uranium ...').
    name = await _resolve_name(ticker, name or "")
    # Query strategy: cleaned name + ticker sharpens well-known stocks (SNDK,
    # IOVA), but an obscure ETF ticker (FLXT) poisons recall — so if that comes
    # back thin, fall back to the cleaned name alone (its geography/theme).
    base = _clean_name(name) if name else ticker
    tk_up = (ticker or "").upper()
    q = f"{base} {ticker}".strip() if base and base.upper() != tk_up else (base or ticker)
    results = await websearch.search(q, max_results=10, days=45)
    if len(results) < 3 and base and base.upper() != tk_up:
        alt = await websearch.search(base, max_results=10, days=45)
        if len(alt) > len(results):
            results = alt
    if not results:
        return None

    src_lines = "\n".join(
        f"[{i+1}] {r['title']}" + (f" ({r['content']})" if r.get("content") else "")
        for i, r in enumerate(results)
    )
    system = (
        "Eres un analista financiero. Con SOLO los titulares de noticias recientes que se te dan, "
        "resume el ENTORNO de un activo para un inversor. Español, conciso, sin relleno. "
        "Prohibido inventar: usa únicamente lo que aparezca en los titulares; si no hay nada "
        "relevante o son escasos, dilo claramente (mejor 'poca información' que especular)."
    )
    user = (
        f"Activo: {name or ticker} ({ticker})\n\nTitulares recientes:\n{src_lines}\n\n"
        "Devuelve EXACTAMENTE este formato:\n"
        "VEREDICTO: favorable | neutral | adverso (una palabra sobre el ENTORNO)\n"
        "CATALIZADORES: 1-3 bullets concretos (con fecha/dato si aparece)\n"
        "RIESGOS: 1-3 bullets (competencia, sector, regulación, disrupción)\n"
        "RESUMEN: 1-2 frases con la lectura del entorno.\n"
        "Cita las fuentes por su número [n] donde corresponda."
    )
    try:
        resp = await get_llm_client().generate(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            # gemini-2.5-flash reasons before answering and reasoning tokens count
            # against this budget — keep it high enough that the visible brief
            # isn't truncated after the thinking phase.
            max_tokens=2048, temperature=0.3,
        )
        md = (resp.text or "").strip()
        if not md:
            return None
    except Exception as exc:
        logger.warning("catalyst brief LLM failed for {}: {}", ticker, exc)
        return None

    verdict = "neutral"
    for line in md.splitlines():
        if line.strip().lower().startswith("veredicto:"):
            v = line.split(":", 1)[1].strip().lower()
            verdict = "favorable" if "favor" in v else "adverso" if "advers" in v else "neutral"
            break
    return {
        "ticker": (ticker or "").upper(),
        "name": name or ticker,
        "verdict": verdict,
        "summary_md": md,
        "sources": [{"title": r["title"], "url": r["url"]} for r in results if r.get("url")][:5],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def refresh_briefs(assets: list[dict]) -> dict:
    """Generate/refresh briefs for a list of {ticker, name}. Skips ones still fresh.
    Caps at _MAX_PER_RUN to protect the search quota. Returns a small summary."""
    if not websearch.enabled():
        return {"status": "búsqueda de noticias no disponible"}
    items = await _load()
    done = 0
    for a in assets:
        if done >= _MAX_PER_RUN:
            break
        tk = (a.get("ticker") or "").upper()
        if not tk:
            continue
        existing = items.get(tk)
        if existing and _fresh(existing):
            continue
        brief = await generate_brief(tk, a.get("name") or tk)
        if brief:
            items[tk] = brief
            done += 1
    if done:
        await _save(items)
    return {"generated": done, "total_cached": len(items)}
