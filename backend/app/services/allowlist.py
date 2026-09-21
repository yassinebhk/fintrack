"""Who's allowed to log in (JsonCache-backed, DB-editable allowlist).

Genuinely global config (not per-user data): a single admin-managed list that
gates login for everyone, so one shared JsonCache key is correct here — this
is NOT the same bug class as report_prefs.py/allocation.py, which stored
per-user preferences under a global key by mistake.

Source of truth migrates lazily: ALLOWED_EMAILS (env var, deploy-time only)
seeds the list the first time it's read if the DB has nothing yet. Once an
admin adds/removes an email via the admin panel, the DB row exists and
becomes authoritative — the env var is no longer consulted after that."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

_KEY = "allowed_emails"


async def get_allowed_emails() -> set[str]:
    """Lowercased set of emails allowed to log in. Falls back to the
    ALLOWED_EMAILS env var if the DB has no row yet."""
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        if row is not None:
            vals = (row.payload or {}).get("emails", [])
            return {str(e).strip().lower() for e in vals if str(e).strip()}
    except Exception as exc:
        logger.warning("allowlist load failed: {}", exc)

    from app.config import get_settings
    return get_settings().allowed_emails_set


async def _save(emails: set[str]) -> set[str]:
    payload = {"emails": sorted(emails)}
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)
    return emails


async def add_email(email: str) -> set[str]:
    emails = await get_allowed_emails()
    emails.add(email.strip().lower())
    return await _save(emails)


async def remove_email(email: str) -> set[str]:
    emails = await get_allowed_emails()
    emails.discard(email.strip().lower())
    return await _save(emails)


_SIGNUP_KEY = "public_signup_override"


async def get_public_signup() -> bool:
    """Whether ANY Google account can log in (allowlist ignored). Admin-editable
    at runtime; falls back to the PUBLIC_SIGNUP env var if never toggled."""
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _SIGNUP_KEY))).scalar_one_or_none()
        if row is not None and row.payload is not None:
            return bool(row.payload.get("enabled", False))
    except Exception as exc:
        logger.warning("public_signup load failed: {}", exc)

    from app.config import get_settings
    return get_settings().public_signup


async def set_public_signup(enabled: bool) -> bool:
    payload = {"enabled": bool(enabled)}
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_SIGNUP_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)
    return payload["enabled"]
