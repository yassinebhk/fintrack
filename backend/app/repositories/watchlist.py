"""CRUD for the watchlist, scoped to a user."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import Watchlist


class WatchlistRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_all(self) -> list[Watchlist]:
        stmt = (
            select(Watchlist)
            .where(Watchlist.user_id == self.user_id)
            .order_by(Watchlist.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, ticker: str, name: str = "", note: str = "") -> Watchlist:
        ticker = ticker.upper().strip()
        existing = (await self.session.execute(
            select(Watchlist).where(Watchlist.user_id == self.user_id, Watchlist.ticker == ticker)
        )).scalar_one_or_none()
        if existing:
            if name:
                existing.name = name
            if note:
                existing.note = note
            await self.session.flush()
            return existing
        obj = Watchlist(user_id=self.user_id, ticker=ticker, name=name, note=note)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, entry_id: int) -> bool:
        obj = (await self.session.execute(
            select(Watchlist).where(Watchlist.id == entry_id, Watchlist.user_id == self.user_id)
        )).scalar_one_or_none()
        if obj is None:
            return False
        await self.session.delete(obj)
        return True
