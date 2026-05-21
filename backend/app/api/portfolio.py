"""Portfolio endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api", tags=["portfolio"])
_service = PortfolioService()


@router.get("/portfolio")
async def get_portfolio() -> dict:
    try:
        return await _service.calculate_portfolio()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/summary")
async def get_portfolio_summary() -> dict:
    try:
        p = await _service.calculate_portfolio()
        return {
            "total_value": p["total_value"],
            "total_cost": p["total_cost"],
            "total_gain_loss": p["total_gain_loss"],
            "total_gain_loss_pct": p["total_gain_loss_pct"],
            "daily_change": p["daily_change"],
            "daily_change_pct": p["daily_change_pct"],
            "base_currency": p["base_currency"],
            "positions_count": len(p["positions"]),
            "last_updated": p["last_updated"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/history")
async def get_portfolio_history(days: int = Query(default=365, ge=1, le=3650)) -> dict:
    history = await _service.get_portfolio_history(days)
    return {"history": history, "days": days}


@router.get("/portfolio/kpis")
async def get_portfolio_kpis() -> dict:
    p = await _service.calculate_portfolio()
    return p["kpis"]


@router.get("/distributions")
async def get_distributions() -> dict:
    p = await _service.calculate_portfolio()
    return {
        "by_type": p["by_type"],
        "by_broker": p["by_broker"],
        "by_currency": p["by_currency"],
    }


@router.post("/refresh")
async def refresh_data() -> dict:
    from datetime import datetime, timezone

    p = await _service.calculate_portfolio()
    return {
        "message": "Data refreshed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_value": p["total_value"],
    }
