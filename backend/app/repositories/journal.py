"""CRUD for the reasoned trade journal, scoped to a user."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry


class JournalRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_all(self, limit: int | None = None) -> list[JournalEntry]:
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.user_id == self.user_id)
            .order_by(JournalEntry.created_at.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, entry_id: int) -> JournalEntry | None:
        stmt = select(JournalEntry).where(
            JournalEntry.id == entry_id, JournalEntry.user_id == self.user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, **values) -> JournalEntry:
        values["user_id"] = self.user_id
        if values.get("ticker"):
            values["ticker"] = str(values["ticker"]).upper().strip()
        obj = JournalEntry(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def review(self, entry_id: int, outcome: str, lesson: str,
                     review_price: float | None = None) -> JournalEntry | None:
        obj = await self.get(entry_id)
        if obj is None:
            return None
        obj.outcome = outcome
        obj.lesson = lesson
        obj.review_price = review_price
        obj.status = "revisada"
        obj.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return obj

    async def delete(self, entry_id: int) -> bool:
        obj = await self.get(entry_id)
        if obj is None:
            return False
        await self.session.delete(obj)
        return True
