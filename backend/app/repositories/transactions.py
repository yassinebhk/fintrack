"""CRUD for transactions, scoped to a user."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_all(self, limit: int | None = None) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == self.user_id)
            .order_by(Transaction.executed_at.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_ticker(self, ticker: str, broker: str | None = None) -> list[Transaction]:
        stmt = select(Transaction).where(
            Transaction.user_id == self.user_id, Transaction.ticker == ticker.upper()
        )
        if broker:
            stmt = stmt.where(Transaction.broker == broker)
        stmt = stmt.order_by(Transaction.executed_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, **values) -> Transaction:
        values["ticker"] = values["ticker"].upper().strip()
        values["user_id"] = self.user_id
        if "executed_at" in values and isinstance(values["executed_at"], str):
            values["executed_at"] = datetime.fromisoformat(values["executed_at"])
        obj = Transaction(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_external_id(self, external_id: str) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.user_id == self.user_id, Transaction.external_id == external_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, tx_id: int) -> bool:
        stmt = select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == self.user_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True
