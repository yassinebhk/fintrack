"""CRUD for transactions."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, limit: int | None = None) -> list[Transaction]:
        stmt = select(Transaction).order_by(Transaction.executed_at.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_ticker(self, ticker: str, broker: str | None = None) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.ticker == ticker.upper())
        if broker:
            stmt = stmt.where(Transaction.broker == broker)
        stmt = stmt.order_by(Transaction.executed_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, **values) -> Transaction:
        values["ticker"] = values["ticker"].upper().strip()
        if "executed_at" in values and isinstance(values["executed_at"], str):
            values["executed_at"] = datetime.fromisoformat(values["executed_at"])
        obj = Transaction(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_external_id(self, external_id: str) -> Transaction | None:
        stmt = select(Transaction).where(Transaction.external_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, tx_id: int) -> bool:
        obj = await self.session.get(Transaction, tx_id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True
