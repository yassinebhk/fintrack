"""Transaction history endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories import PositionRepository, TransactionRepository

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionIn(BaseModel):
    type: str  # buy, sell, dividend, fee, deposit, withdrawal
    ticker: str
    quantity: float
    price: float
    fee: float = 0.0
    currency: str = "EUR"
    broker: str
    executed_at: str  # ISO datetime
    notes: str | None = None


@router.get("")
async def list_transactions(
    limit: int = 200,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await TransactionRepository(session).list_all(limit=limit)
    return [
        {
            "id": r.id,
            "type": r.type,
            "ticker": r.ticker,
            "quantity": r.quantity,
            "price": r.price,
            "fee": r.fee,
            "currency": r.currency,
            "broker": r.broker,
            "executed_at": r.executed_at.isoformat(),
            "notes": r.notes,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("")
async def add_transaction(payload: TransactionIn, session: AsyncSession = Depends(get_session)) -> dict:
    tx_repo = TransactionRepository(session)
    pos_repo = PositionRepository(session)

    try:
        executed = datetime.fromisoformat(payload.executed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid executed_at: {exc}") from exc

    tx = await tx_repo.add(
        type=payload.type,
        ticker=payload.ticker,
        quantity=payload.quantity,
        price=payload.price,
        fee=payload.fee,
        currency=payload.currency,
        broker=payload.broker,
        executed_at=executed.astimezone(timezone.utc),
        notes=payload.notes,
    )

    # Update position based on transaction kind
    if payload.type == "buy":
        existing = await pos_repo.get(payload.ticker, payload.broker)
        if existing:
            new_qty = existing.quantity + payload.quantity
            new_avg = ((existing.quantity * existing.avg_price) + (payload.quantity * payload.price)) / new_qty
            existing.quantity = new_qty
            existing.avg_price = new_avg
        else:
            await pos_repo.upsert(
                ticker=payload.ticker,
                quantity=payload.quantity,
                avg_price=payload.price,
                type="stock",
                currency=payload.currency,
                broker=payload.broker,
                source="manual_tx",
            )
    elif payload.type == "sell":
        existing = await pos_repo.get(payload.ticker, payload.broker)
        if existing:
            new_qty = existing.quantity - payload.quantity
            if new_qty <= 0:
                await pos_repo.delete(payload.ticker, payload.broker)
            else:
                existing.quantity = new_qty

    return {"message": "Transaction added", "id": tx.id}


@router.delete("/{tx_id}")
async def delete_transaction(tx_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    ok = await TransactionRepository(session).delete(tx_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Transaction {tx_id} not found")
    return {"message": f"Transaction {tx_id} deleted"}
