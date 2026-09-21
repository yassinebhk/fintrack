"""User report preferences (JsonCache-backed).

Right now: which tickers to EXCLUDE from daily reports/alerts. Useful for dust
positions (tiny crypto leftovers) whose huge % swings distort the daily stats
even though their euro weight is negligible. They stay in the real portfolio
(Kraken keeps syncing them) — we just hide them from the reports."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

_KEY = "report_excluded_tickers"


async def _resolve_user_id(user_id: int | None) -> int:
    if user_id is not None:
        return user_id
    from app.auth import get_owner_user_id_cached
    return await get_owner_user_id_cached() or 0


async def get_excluded(user_id: int | None = None) -> set[str]:
    """Uppercased set of tickers to hide from daily reports/alerts (empty if unset).

    user_id: whose preferences. Defaults to the owner — this preserves existing
    owner-only callers (Telegram bot, alerts engine) unchanged. Any caller acting
    on behalf of a logged-in HTTP user MUST pass current_user.id explicitly
    (2026-09-21 security fix: this was a single global key shared by every
    logged-in user, so one user's exclusions applied to — and could be
    overwritten by — everyone else's)."""
    uid = await _resolve_user_id(user_id)
    key = f"{_KEY}:{uid}"
    try:
        from sqlalchemy import select
        from app.auth import get_owner_user_id_cached
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == key))).scalar_one_or_none()
            if row is None and uid == (await get_owner_user_id_cached() or 0):
                # Read-fallback to the pre-migration global key so the owner's
                # already-configured exclusions (e.g. dust DOGE/SOL/ETH) survive
                # the 2026-09-21 per-user namespacing — copied forward on next save.
                row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        vals = (row.payload or {}).get("tickers", []) if row and row.payload else []
        return {str(t).upper() for t in vals}
    except Exception as exc:
        logger.warning("report_prefs load failed: {}", exc)
        return set()


async def set_excluded(tickers: list[str], user_id: int | None = None) -> dict:
    uid = await _resolve_user_id(user_id)
    key = f"{_KEY}:{uid}"
    payload = {"tickers": sorted({str(t).upper().strip() for t in tickers if str(t).strip()})}
    try:
        from app.db import session_scope, upsert_insert
        from app.models import JsonCache
        stmt = upsert_insert()(JsonCache).values(
            key=key, payload=payload, updated_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(index_elements=["key"],
                                set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
        async with session_scope() as s:
            await s.execute(stmt)
    except Exception as exc:
        logger.exception("report_prefs save failed")
        raise
    return payload
