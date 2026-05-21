"""Broker sync endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.broker_sync import BrokerSync
from app.services.brokers import KrakenService
from app.services.brokers.kraken import KrakenAPIError, KrakenAuthError

router = APIRouter(prefix="/api/brokers", tags=["brokers"])


@router.post("/kraken/sync")
async def kraken_sync(session: AsyncSession = Depends(get_session)) -> dict:
    settings = get_settings()
    if not settings.has_kraken:
        raise HTTPException(status_code=400, detail="Kraken API key/secret not configured")

    try:
        service = KrakenService()
    except KrakenAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await service.sync_all(session)
    except KrakenAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("kraken sync failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": "Kraken sync completed", "result": result}


@router.get("/kraken/balance")
async def kraken_balance() -> dict:
    """Live balances from Kraken, without persisting. Useful for sanity checks."""
    settings = get_settings()
    if not settings.has_kraken:
        raise HTTPException(status_code=400, detail="Kraken not configured")
    try:
        service = KrakenService()
        balances = await service.get_balance()
    except KrakenAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KrakenAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"balances": balances}


@router.get("/syncs")
async def list_syncs(limit: int = 20, session: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(BrokerSync).order_by(BrokerSync.started_at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [
        {
            "id": r.id,
            "broker": r.broker,
            "status": r.status,
            "positions_synced": r.positions_synced,
            "transactions_synced": r.transactions_synced,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]
