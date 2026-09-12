"""Reasoned trade journal endpoints — a decision logged with its rationale, then
reviewed later with an outcome and a lesson. Direct user actions (same criterion as
positions/daytrading), scoped to the logged-in user."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import session_scope
from app.models.user import User
from app.repositories import JournalRepository

router = APIRouter(prefix="/api/journal", tags=["journal"])


def _to_dict(e) -> dict:
    return {
        "id": e.id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "ticker": e.ticker, "name": e.name, "action": e.action,
        "conviction": e.conviction, "horizon": e.horizon, "thesis": e.thesis,
        "target_price": e.target_price, "stop_price": e.stop_price, "entry_price": e.entry_price,
        "status": e.status,
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
        "review_price": e.review_price, "outcome": e.outcome, "lesson": e.lesson,
    }


class EntryIn(BaseModel):
    ticker: str = Field(default="", max_length=32)
    name: str = Field(default="", max_length=128)
    action: str = Field(default="compra", pattern="^(compra|venta|mantener|vigilar)$")
    conviction: str = Field(default="media", pattern="^(alta|media|baja)$")
    horizon: str = Field(default="", max_length=48)
    thesis: str = Field(min_length=10, description="Por qué tomas esta decisión — antes de saber el resultado")
    target_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)


class ReviewIn(BaseModel):
    outcome: str = Field(pattern="^(acierto|fallo|neutral)$")
    lesson: str = Field(min_length=3, description="Qué aprendiste")


async def _price(ticker: str) -> float | None:
    if not ticker:
        return None
    try:
        from app.services.market.yahoo_finance import YahooFinanceService
        p = await YahooFinanceService().get_price(ticker)
        return p.get("price") if p else None
    except Exception:
        return None


@router.get("")
async def list_entries(current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        entries = await JournalRepository(s, current_user.id).list_all(limit=200)
        return {"entries": [_to_dict(e) for e in entries]}


@router.post("", status_code=201)
async def add_entry(payload: EntryIn, current_user: User = Depends(get_current_user)) -> dict:
    entry_price = await _price(payload.ticker)
    async with session_scope() as s:
        e = await JournalRepository(s, current_user.id).add(
            ticker=payload.ticker, name=payload.name, action=payload.action,
            conviction=payload.conviction, horizon=payload.horizon, thesis=payload.thesis,
            target_price=payload.target_price, stop_price=payload.stop_price,
            entry_price=entry_price,
        )
        return _to_dict(e)


@router.post("/{entry_id}/review")
async def review_entry(entry_id: int, payload: ReviewIn,
                       current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        repo = JournalRepository(s, current_user.id)
        existing = await repo.get(entry_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Entrada no encontrada")
        review_price = await _price(existing.ticker)
        e = await repo.review(entry_id, payload.outcome, payload.lesson, review_price)
        return _to_dict(e)


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int, current_user: User = Depends(get_current_user)) -> dict:
    async with session_scope() as s:
        ok = await JournalRepository(s, current_user.id).delete(entry_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Entrada no encontrada")
        return {"deleted": True}
