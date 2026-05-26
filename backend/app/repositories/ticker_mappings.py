"""CRUD for ISIN / problematic ticker mappings."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import upsert_insert
from app.models.ticker_mapping import TickerMapping


class TickerMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, source_ticker: str) -> str:
        """Return target ticker, falling back to source unchanged."""
        stmt = select(TickerMapping).where(TickerMapping.source_ticker == source_ticker)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.target_ticker if row else source_ticker

    async def get(self, source_ticker: str) -> TickerMapping | None:
        stmt = select(TickerMapping).where(TickerMapping.source_ticker == source_ticker)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        source_ticker: str,
        target_ticker: str,
        provider: str = "yahoo",
        asset_type: str | None = None,
        asset_name: str | None = None,
        notes: str | None = None,
    ) -> None:
        stmt = upsert_insert()(TickerMapping).values(
            source_ticker=source_ticker,
            target_ticker=target_ticker,
            provider=provider,
            asset_type=asset_type,
            asset_name=asset_name,
            notes=notes,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_ticker"],
            set_={
                "target_ticker": stmt.excluded.target_ticker,
                "provider": stmt.excluded.provider,
                "asset_type": stmt.excluded.asset_type,
                "asset_name": stmt.excluded.asset_name,
                "notes": stmt.excluded.notes,
            },
        )
        await self.session.execute(stmt)

    async def list_all(self) -> list[TickerMapping]:
        stmt = select(TickerMapping).order_by(TickerMapping.source_ticker)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
