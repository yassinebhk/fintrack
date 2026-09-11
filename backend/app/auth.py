"""Google OAuth login + per-request current-user resolution.

Session-cookie based (Starlette SessionMiddleware, signed with SESSION_SECRET_KEY) —
the cookie only ever holds a `user_id`, never a token. Frontend and backend are
same-origin in production, so no cross-origin cookie concerns.

`get_owner_user_id()` exists for features not yet generalized per-user (Fase 2):
opportunities' "exclude what you hold", the daily briefing, the alerts engine,
Kraken sync, and the Telegram bot all keep operating on the original single
owner's account until they're rewritten to loop over every user.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.user import User

_oauth = OAuth()
_oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def google_client():
    settings = get_settings()
    _oauth.google.client_id = settings.google_client_id
    _oauth.google.client_secret = settings.google_client_secret
    return _oauth.google


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No autenticado")
    user = await session.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sesión inválida")
    return user


async def get_current_user_optional(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return await session.get(User, user_id)


async def get_owner_user_id(session: AsyncSession) -> int | None:
    """Resolve the original owner's user id for features not yet per-user (Fase 2)."""
    settings = get_settings()
    if not settings.owner_email:
        return None
    result = await session.execute(
        select(User.id).where(User.email == settings.owner_email.strip().lower())
    )
    owner_id = result.scalar_one_or_none()
    if owner_id is None:
        logger.warning("owner_email {} set but no matching User row found", settings.owner_email)
    return owner_id


_owner_id_cache: int | None = None


async def get_owner_user_id_cached() -> int | None:
    """Same as get_owner_user_id, but memoized process-wide (owner's id never
    changes once created) — for services that resolve it outside a request's
    own DB session (scheduler jobs, Telegram bot, briefing/alerts)."""
    global _owner_id_cache
    if _owner_id_cache is not None:
        return _owner_id_cache
    from app.db import session_scope

    async with session_scope() as session:
        owner_id = await get_owner_user_id(session)
    if owner_id is not None:
        _owner_id_cache = owner_id
    return owner_id
