"""Positions CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories import PositionRepository

router = APIRouter(prefix="/api/positions", tags=["positions"])


class PositionIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    avg_price: float = Field(ge=0)
    type: str
    currency: str = "EUR"
    broker: str


class PositionPatch(BaseModel):
    quantity: float | None = None
    avg_price: float | None = None


@router.get("")
async def list_positions(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = await PositionRepository(session).list_all()
    return [
        {
            "ticker": r.ticker,
            "quantity": r.quantity,
            "avg_price": r.avg_price,
            "type": r.type,
            "currency": r.currency,
            "broker": r.broker,
            "isin": r.isin,
            "asset_name": r.asset_name,
        }
        for r in rows
    ]


@router.post("")
async def create_position(payload: PositionIn, session: AsyncSession = Depends(get_session)) -> dict:
    repo = PositionRepository(session)
    existing = await repo.get(payload.ticker.upper(), payload.broker)
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Position {payload.ticker} @ {payload.broker} already exists")
    pos = await repo.upsert(**payload.model_dump(), source="manual")
    return {"message": "Position created", "id": pos.id, "ticker": pos.ticker}


@router.put("/{ticker}")
async def update_position(
    ticker: str,
    payload: PositionPatch,
    broker: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = PositionRepository(session)
    ticker = ticker.upper()

    if broker:
        existing = await repo.get(ticker, broker)
    else:
        rows = [p for p in await repo.list_all() if p.ticker == ticker]
        existing = rows[0] if rows else None
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Position {ticker} not found")

    if payload.quantity is not None:
        existing.quantity = payload.quantity
    if payload.avg_price is not None:
        existing.avg_price = payload.avg_price
    await session.flush()
    return {"message": "Position updated", "ticker": ticker}


@router.delete("/{ticker}")
async def delete_position(
    ticker: str,
    broker: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = PositionRepository(session)
    ticker = ticker.upper()
    if broker:
        ok = await repo.delete(ticker, broker)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Position {ticker} @ {broker} not found")
        return {"message": "Position deleted", "ticker": ticker, "broker": broker}

    rows = [p for p in await repo.list_all() if p.ticker == ticker]
    if not rows:
        raise HTTPException(status_code=404, detail=f"Position {ticker} not found")
    for r in rows:
        await repo.delete(r.ticker, r.broker)
    return {"message": "Position deleted", "ticker": ticker, "brokers_affected": [r.broker for r in rows]}
