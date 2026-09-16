"""Catalyst / environment briefs — the 'what's the fundamental context' layer the
momentum engine lacks. For a held or recommended asset we search the live web
(Tavily) and have the LLM synthesize a short, SOURCED brief: recent catalysts,
environment risks (competition, sector, regulation) and a one-line verdict.

Grounded on REAL web results — if web search isn't configured or returns nothing,
NO brief is produced (we never fabricate a brief from stale model memory). Cached
per ticker for a few days to stay well within the free search quota.
"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from app.llm import LLMMessage, get_llm_client
from app.services import websearch

_KEY = "catalyst_briefs"
_TTL_DAYS = 3
_MAX_PER_RUN = 30   # cap per batch so we never blow the search quota


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
    q = f"{name or ticker} {ticker} stock recent catalysts news outlook risks 2026"
    results = await websearch.search(q, max_results=6, days=45)
    if not results:
        return None

    src_lines = "\n".join(
        f"[{i+1}] {r['title']} — {r['content']}" for i, r in enumerate(results)
    )
    system = (
        "Eres un analista financiero. Con SOLO los resultados web recientes que se te dan, "
        "resume el ENTORNO de un activo para un inversor. Español, conciso, sin relleno. "
        "Prohibido inventar: usa únicamente lo que aparezca en los resultados; si no hay nada "
        "relevante, dilo claramente."
    )
    user = (
        f"Activo: {name or ticker} ({ticker})\n\nResultados web:\n{src_lines}\n\n"
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
            max_tokens=700, temperature=0.3,
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
        return {"status": "web search no configurado (falta TAVILY_API_KEY)"}
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
