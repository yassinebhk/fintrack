"""CRUD for the day-trading paper journal."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.day_trade import DayTrade


class DayTradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_open(self) -> list[DayTrade]:
        stmt = select(DayTrade).where(DayTrade.status == "open").order_by(DayTrade.opened_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, limit: int | None = None) -> list[DayTrade]:
        stmt = select(DayTrade).order_by(DayTrade.opened_at.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_closed(self) -> list[DayTrade]:
        stmt = select(DayTrade).where(DayTrade.status == "closed").order_by(DayTrade.closed_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, trade_id: int) -> DayTrade | None:
        return await self.session.get(DayTrade, trade_id)

    async def add(self, **values) -> DayTrade:
        values["ticker"] = values["ticker"].upper().strip()
        obj = DayTrade(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def close(self, trade_id: int, **values) -> DayTrade | None:
        obj = await self.session.get(DayTrade, trade_id)
        if obj is None:
            return None
        values.setdefault("status", "closed")
        values.setdefault("closed_at", datetime.now(timezone.utc))
        for key, val in values.items():
            setattr(obj, key, val)
        await self.session.flush()
        return obj
