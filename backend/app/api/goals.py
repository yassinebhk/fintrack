"""Financial goals endpoints — direct user actions, scoped to the logged-in
user (same pattern as watchlist.py)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import session_scope
from app.models.user import User
from app.repositories import GoalRepository

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    icon: str = Field(default="🎯", max_length=8)
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0.0, ge=0)
    target_date: date | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=8)
    target_amount: float | None = Field(default=None, gt=0)
    current_amount: float | None = Field(default=None, ge=0)
    target_date: date | None = None


def _row(g) -> dict:
    return {
        "id": g.id, "name": g.name, "icon": g.icon,
        "target_amount": g.target_amount, "current_amount": g.current_amount,
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "progress_pct": round(min(100.0, g.current_amount / g.target_amount * 100), 1) if g.target_amount else 0.0,
        "remaining_eur": round(max(0.0, g.target_amount - g.current_amount), 2),
        "created_at": g.created_at.isoformat(),
    }


@router.get("")
async def list_goals(current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        goals = await GoalRepository(s, current_user.id).list_all()
    return {"goals": [_row(g) for g in goals]}


@router.post("", status_code=201)
async def create_goal(payload: GoalIn, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        g = await GoalRepository(s, current_user.id).add(
            name=payload.name, target_amount=payload.target_amount, icon=payload.icon,
            current_amount=payload.current_amount, target_date=payload.target_date,
        )
        await s.flush()
        row = _row(g)
    return row


@router.put("/{goal_id}")
async def update_goal(goal_id: int, payload: GoalUpdate, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        g = await GoalRepository(s, current_user.id).update(goal_id, **payload.model_dump(exclude_unset=True))
        if g is None:
            raise HTTPException(status_code=404, detail="Objetivo no encontrado")
        row = _row(g)
    return row


@router.delete("/{goal_id}")
async def delete_goal(goal_id: int, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        ok = await GoalRepository(s, current_user.id).delete(goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return {"status": "deleted"}
