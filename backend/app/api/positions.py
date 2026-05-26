"""Positions CRUD endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories import PositionRepository, TransactionRepository
from app.services.market import CoinGeckoService, YahooFinanceService

router = APIRouter(prefix="/api/positions", tags=["positions"])

_yahoo = YahooFinanceService()
_coingecko = CoinGeckoService()


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


class ContributionIn(BaseModel):
    broker: str
    eur_amount: float = Field(gt=0, description="Euros aportados al fondo/activo")


async def _current_price(ticker: str, asset_type: str) -> float | None:
    if asset_type == "crypto":
        p = await _coingecko.get_price(ticker, vs_currency="eur")
        if p is None:
            p = await _yahoo.get_price(f"{ticker.upper()}-EUR")
    else:
        p = await _yahoo.get_price(ticker)
    return p.get("price") if p else None


@router.post("/{ticker}/contribute")
async def contribute(
    ticker: str,
    payload: ContributionIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Add money (in EUR) to an existing position. Shares are computed from the
    live price so the user never has to figure out units themselves."""
    repo = PositionRepository(session)
    ticker = ticker.upper()
    pos = await repo.get(ticker, payload.broker)
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position {ticker} @ {payload.broker} not found")

    price = await _current_price(ticker, pos.type)
    if not price or price <= 0:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener el precio actual de {ticker}")

    shares_added = payload.eur_amount / price
    old_qty = pos.quantity
    old_cost = old_qty * pos.avg_price
    new_qty = old_qty + shares_added
    # New average price weights the prior cost with the freshly contributed euros
    new_avg = (old_cost + payload.eur_amount) / new_qty if new_qty > 0 else price

    pos.quantity = new_qty
    pos.avg_price = new_avg
    await session.flush()

    # Record the contribution as a buy transaction for the audit trail
    try:
        await TransactionRepository(session).add(
            type="buy",
            ticker=ticker,
            quantity=shares_added,
            price=price,
            currency=pos.currency,
            broker=payload.broker,
            executed_at=datetime.now(timezone.utc),
            notes=f"Aportación de {payload.eur_amount:.2f} € ({shares_added:.6f} part. @ {price:.4f})",
        )
    except Exception as exc:
        logger.warning("could not record contribution tx: {}", exc)

    return {
        "message": "Aportación registrada",
        "ticker": ticker,
        "broker": payload.broker,
        "eur_added": payload.eur_amount,
        "price_used": round(price, 4),
        "shares_added": round(shares_added, 8),
        "new_quantity": round(new_qty, 8),
        "new_avg_price": round(new_avg, 4),
    }


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
