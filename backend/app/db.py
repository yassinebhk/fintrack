"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

# Managed Postgres / CockroachDB over asyncpg needs TLS, and CockroachDB also
# requires asyncpg's prepared-statement cache disabled (it errors otherwise).
# Encrypt without cert verification → no CA file to ship to Render; channel is
# still encrypted. (SQLite local dev path keeps connect_args empty.)
_connect_args: dict = {}
if "asyncpg" in _settings.async_database_url:
    import ssl as _ssl

    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    _connect_args = {"ssl": _ctx, "statement_cache_size": 0}

engine = create_async_engine(
    _settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def upsert_insert():
    """Return the dialect-appropriate INSERT that supports ON CONFLICT.

    SQLite and PostgreSQL both expose on_conflict_do_update with the same
    API, but the constructor lives in different dialect modules.
    """
    url = _settings.database_url
    if url.startswith("postgresql") or "+asyncpg" in url or "+psycopg" in url:
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session that auto-commits on success and rolls back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for request-scoped sessions."""
    async with session_scope() as session:
        yield session


async def init_db() -> None:
    """Create all tables (use Alembic for migrations once schema stabilizes)."""
    from app import models  # noqa: F401  ensure models are imported

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
