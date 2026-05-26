"""Backtest lab endpoints."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.backtest import BacktestSpec, STRATEGIES, run_backtest

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy: str = Field(..., description="Strategy key (see /api/backtest/strategies)")
    tickers: list[str] = Field(..., min_length=1)
    asset_types: dict[str, str] = Field(
        default_factory=dict,
        description="Map ticker → 'crypto' | 'stock' | 'etf' | 'fund'. Defaults to 'stock'.",
    )
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str | None = None
    params: dict | None = None


@router.get("/strategies")
async def list_strategies() -> dict:
    """List available strategies with parameter specs."""
    return {
        "strategies": [
            {
                "key": s.key,
                "name": s.name,
                "description": s.description,
                "default_params": s.params,
                "param_specs": s.param_specs,
            }
            for s in STRATEGIES.values()
        ],
    }


@router.post("/run")
async def run(request: BacktestRequest) -> dict:
    spec = BacktestSpec(
        strategy_key=request.strategy,
        tickers=[t.upper() for t in request.tickers],
        asset_types={t.upper(): v for t, v in request.asset_types.items()},
        start_date=request.start_date,
        end_date=request.end_date,
        params=request.params or {},
    )
    try:
        result = await run_backtest(spec)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("backtest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "strategy": result.strategy_key,
        "tickers": result.tickers,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "metrics": result.metrics,
        "equity_curve": result.equity_curve,
        "trades": result.trades,
    }
