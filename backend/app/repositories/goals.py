"""CRUD for financial goals, scoped to a user."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal


class GoalRepository:
    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    async def list_all(self) -> list[Goal]:
        stmt = select(Goal).where(Goal.user_id == self.user_id).order_by(Goal.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(
        self, name: str, target_amount: float, icon: str = "🎯",
        current_amount: float = 0.0, target_date: date | None = None,
    ) -> Goal:
        obj = Goal(
            user_id=self.user_id, name=name.strip(), icon=(icon or "🎯").strip() or "🎯",
            target_amount=target_amount, current_amount=current_amount, target_date=target_date,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, goal_id: int, **fields) -> Goal | None:
        obj = (await self.session.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == self.user_id)
        )).scalar_one_or_none()
        if obj is None:
            return None
        for k, v in fields.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        await self.session.flush()
        return obj

    async def delete(self, goal_id: int) -> bool:
        obj = (await self.session.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == self.user_id)
        )).scalar_one_or_none()
        if obj is None:
            return False
        await self.session.delete(obj)
        return True
