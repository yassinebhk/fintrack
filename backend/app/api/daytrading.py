"""Day-trading paper journal endpoints. No secret gate — these are direct user
actions (same criterion as app.api.positions), not admin/cron-triggered jobs."""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/daytrading", tags=["daytrading"])


class TradeIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    direction: str = Field(default="long", pattern="^(long|short)$")
    thesis: str = Field(min_length=1)
    stake_eur: float = Field(gt=0)
    stop_loss_pct: float = Field(gt=0)
    take_profit_pct: float | None = Field(default=None, gt=0)
    conviction: str = Field(default="media")
    news_url: str | None = None
    name: str = ""


@router.post("/trades", status_code=201)
async def open_trade(payload: TradeIn) -> dict:
    from app.services.daytrading import journal
    try:
        return await journal.open_trade(
            ticker=payload.ticker,
            direction=payload.direction,
            thesis=payload.thesis,
            stake_eur=payload.stake_eur,
            stop_loss_pct=payload.stop_loss_pct,
            take_profit_pct=payload.take_profit_pct,
            conviction=payload.conviction,
            news_url=payload.news_url,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trades/{trade_id}/close")
async def close_trade(trade_id: int) -> dict:
    from app.services.daytrading import journal
    try:
        trade = await journal.close_trade(trade_id, reason="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if trade is None:
        raise HTTPException(status_code=404, detail="Operación no encontrada o ya cerrada")
    return trade


@router.post("/mark")
async def mark_open_trades() -> dict:
    from app.services.daytrading import journal

    async def _job():
        try:
            await journal.mark_open_trades()
        except Exception:
            logger.exception("day trading mark failed")
    asyncio.create_task(_job())
    return {"status": "accepted"}


@router.get("/trades")
async def list_trades(status: str = Query(default="all", pattern="^(open|closed|all)$")) -> dict:
    from app.services.daytrading import journal
    trades = await journal.list_trades(status)
    return {"count": len(trades), "trades": trades}


@router.get("/report")
async def report() -> dict:
    from app.services.daytrading import journal
    return await journal.report()
