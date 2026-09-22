"""CRUD for watchlist pins (per-ticker price snapshots), scoped to a user."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist_pin import WatchlistPin


class WatchlistPinRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_for_ticker(self, ticker: str) -> list[WatchlistPin]:
        stmt = (
            select(WatchlistPin)
            .where(WatchlistPin.user_id == self.user_id, WatchlistPin.ticker == ticker.upper().strip())
            .order_by(WatchlistPin.pinned_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, ticker: str, price: float | None, currency: str | None, note: str | None) -> WatchlistPin:
        obj = WatchlistPin(
            user_id=self.user_id, ticker=ticker.upper().strip(),
            price=price, currency=currency, note=note or None,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, pin_id: int) -> bool:
        obj = (await self.session.execute(
            select(WatchlistPin).where(WatchlistPin.id == pin_id, WatchlistPin.user_id == self.user_id)
        )).scalar_one_or_none()
        if obj is None:
            return False
        await self.session.delete(obj)
        return True
