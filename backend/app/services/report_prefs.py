"""User report preferences (JsonCache-backed).

Right now: which tickers to EXCLUDE from daily reports/alerts. Useful for dust
positions (tiny crypto leftovers) whose huge % swings distort the daily stats
even though their euro weight is negligible. They stay in the real portfolio
(Kraken keeps syncing them) — we just hide them from the reports."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

_KEY = "report_excluded_tickers"


async def get_excluded() -> set[str]:
    """Uppercased set of tickers to hide from daily reports/alerts (empty if unset)."""
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        vals = (row.payload or {}).get("tickers", []) if row and row.payload else []
        return {str(t).upper() for t in vals}
    except Exception as exc:
        logger.warning("report_prefs load failed: {}", exc)
        return set()


async def set_excluded(tickers: list[str]) -> dict:
    payload = {"tickers": sorted({str(t).upper().strip() for t in tickers if str(t).strip()})}
    try:
        from app.db import session_scope, upsert_insert
        from app.models import JsonCache
        stmt = upsert_insert()(JsonCache).values(
            key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(index_elements=["key"],
                                set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
        async with session_scope() as s:
            await s.execute(stmt)
    except Exception as exc:
        logger.exception("report_prefs save failed")
        raise
    return payload
