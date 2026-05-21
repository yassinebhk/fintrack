"""CRUD for cached spot prices."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_cache import PriceCache


class PriceCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, ticker: str, source: str) -> PriceCache | None:
        stmt = (
            select(PriceCache)
            .where(PriceCache.ticker == ticker.upper(), PriceCache.source == source)
            .order_by(PriceCache.fetched_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fresh(self, ticker: str, source: str) -> PriceCache | None:
        """Returns cached price only if still inside TTL."""
        row = await self.get(ticker, source)
        if row is None:
            return None
        if row.expires_at < datetime.now(timezone.utc):
            return None
        return row

    async def upsert(
        self,
        ticker: str,
        source: str,
        price: float,
        previous_close: float,
        currency: str,
        name: str | None = None,
        market_cap: float = 0.0,
        volume_24h: float = 0.0,
        ttl: timedelta = timedelta(minutes=15),
    ) -> PriceCache:
        now = datetime.now(timezone.utc)
        existing = await self.get(ticker, source)
        if existing:
            existing.price = price
            existing.previous_close = previous_close
            existing.currency = currency
            existing.name = name or existing.name
            existing.market_cap = market_cap
            existing.volume_24h = volume_24h
            existing.fetched_at = now
            existing.expires_at = now + ttl
            await self.session.flush()
            return existing
        obj = PriceCache(
            ticker=ticker.upper(),
            source=source,
            price=price,
            previous_close=previous_close,
            currency=currency,
            name=name,
            market_cap=market_cap,
            volume_24h=volume_24h,
            fetched_at=now,
            expires_at=now + ttl,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def purge_expired(self) -> int:
        stmt = delete(PriceCache).where(PriceCache.expires_at < datetime.now(timezone.utc))
        result = await self.session.execute(stmt)
        return result.rowcount or 0
