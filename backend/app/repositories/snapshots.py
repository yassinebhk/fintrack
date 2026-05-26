"""CRUD for daily portfolio snapshots."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import upsert_insert
from app.models.snapshot import Snapshot


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_today(
        self,
        snapshot_date: date,
        total_value: float,
        total_cost: float = 0.0,
        total_gain_loss: float = 0.0,
        daily_change: float = 0.0,
    ) -> None:
        stmt = upsert_insert()(Snapshot).values(
            snapshot_date=snapshot_date,
            total_value=total_value,
            total_cost=total_cost,
            total_gain_loss=total_gain_loss,
            daily_change=daily_change,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["snapshot_date"],
            set_={
                "total_value": stmt.excluded.total_value,
                "total_cost": stmt.excluded.total_cost,
                "total_gain_loss": stmt.excluded.total_gain_loss,
                "daily_change": stmt.excluded.daily_change,
            },
        )
        await self.session.execute(stmt)

    async def list_last_days(self, days: int) -> list[Snapshot]:
        cutoff = date.today() - timedelta(days=days)
        stmt = (
            select(Snapshot)
            .where(Snapshot.snapshot_date >= cutoff)
            .order_by(Snapshot.snapshot_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Snapshot]:
        stmt = select(Snapshot).order_by(Snapshot.snapshot_date.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
