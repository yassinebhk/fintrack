"""CRUD for positions, scoped to an async session AND a user."""

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import upsert_insert
from app.models.position import Position


class PositionRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_all(self) -> list[Position]:
        result = await self.session.execute(
            select(Position)
            .where(Position.user_id == self.user_id)
            .order_by(Position.broker, Position.ticker)
        )
        return list(result.scalars().all())

    async def get(self, ticker: str, broker: str) -> Position | None:
        stmt = select(Position).where(
            Position.user_id == self.user_id, Position.ticker == ticker, Position.broker == broker
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, **values) -> Position:
        """Insert or update a position by (user_id, ticker, broker)."""
        required = {"ticker", "quantity", "avg_price", "type", "currency", "broker"}
        missing = required - values.keys()
        if missing:
            raise ValueError(f"upsert: missing required fields {missing}")

        ticker = values["ticker"].upper().strip()
        broker = values["broker"].strip()
        values["ticker"] = ticker
        values["broker"] = broker
        values["user_id"] = self.user_id

        existing = await self.get(ticker, broker)
        if existing is None:
            obj = Position(**values)
            self.session.add(obj)
            await self.session.flush()
            return obj

        for k, v in values.items():
            setattr(existing, k, v)
        await self.session.flush()
        return existing

    async def bulk_upsert(self, rows: Iterable[dict]) -> int:
        """Bulk insert/update; returns number of affected rows."""
        rows = [{**r, "user_id": self.user_id} for r in rows]
        if not rows:
            return 0
        stmt = upsert_insert()(Position).values(rows)
        update_cols = {
            c.name: c
            for c in stmt.excluded
            if c.name not in {"id", "created_at", "user_id", "ticker", "broker"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "ticker", "broker"],
            set_=update_cols,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or len(rows)

    async def delete(self, ticker: str, broker: str) -> bool:
        existing = await self.get(ticker, broker)
        if existing is None:
            return False
        await self.session.delete(existing)
        await self.session.flush()
        return True

    async def delete_by_broker(self, broker: str) -> int:
        stmt = delete(Position).where(Position.user_id == self.user_id, Position.broker == broker)
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def count(self) -> int:
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count(Position.id)).where(Position.user_id == self.user_id)
        )
        return result.scalar_one()
