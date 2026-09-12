"""Portfolio endpoints — scoped to the logged-in user."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.models.user import User
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api", tags=["portfolio"])


def _get_service(current_user: User = Depends(get_current_user)) -> PortfolioService:
    return PortfolioService(current_user.id)


@router.get("/portfolio")
async def get_portfolio(svc: PortfolioService = Depends(_get_service)) -> dict:
    try:
        return await svc.calculate_portfolio()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/summary")
async def get_portfolio_summary(svc: PortfolioService = Depends(_get_service)) -> dict:
    try:
        p = await svc.calculate_portfolio()
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


@router.get("/portfolio/risk-analysis")
async def get_risk_analysis(svc: PortfolioService = Depends(_get_service)) -> dict:
    try:
        return await svc.risk_analysis()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/risk-metrics")
async def get_portfolio_risk_metrics(svc: PortfolioService = Depends(_get_service)) -> dict:
    """Book-level risk metrics (vol, Sortino, VaR/CVaR, max DD, Calmar, beta/alpha)."""
    try:
        return await svc.portfolio_risk_metrics()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/catalysts")
async def get_portfolio_catalysts(svc: PortfolioService = Depends(_get_service)) -> dict:
    """Upcoming earnings / ex-dividend dates for held assets, soonest first."""
    try:
        return {"events": await svc.get_holdings_catalysts()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/attribution")
async def get_portfolio_attribution(svc: PortfolioService = Depends(_get_service)) -> dict:
    """Contribution to total P/L per holding and per asset type."""
    try:
        return await svc.performance_attribution()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/history")
async def get_portfolio_history(
    days: int = Query(default=365, ge=1, le=3650), svc: PortfolioService = Depends(_get_service)
) -> dict:
    history = await svc.get_portfolio_history(days)
    return {"history": history, "days": days}


@router.get("/portfolio/position-history/{ticker}")
async def get_position_history(
    ticker: str, days: int = Query(default=365, ge=1, le=3650), svc: PortfolioService = Depends(_get_service)
) -> dict:
    try:
        return await svc.get_position_history(ticker, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/kpis")
async def get_portfolio_kpis(svc: PortfolioService = Depends(_get_service)) -> dict:
    p = await svc.calculate_portfolio()
    return p["kpis"]


@router.get("/distributions")
async def get_distributions(svc: PortfolioService = Depends(_get_service)) -> dict:
    p = await svc.calculate_portfolio()
    return {
        "by_type": p["by_type"],
        "by_broker": p["by_broker"],
        "by_currency": p["by_currency"],
    }


@router.api_route("/refresh", methods=["GET", "POST"])
async def refresh_data(svc: PortfolioService = Depends(_get_service)) -> dict:
    """Force a portfolio recalculation. Accepts GET (legacy frontend) and POST."""
    from datetime import datetime, timezone

    p = await svc.calculate_portfolio()
    return {
        "message": "Data refreshed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_value": p["total_value"],
    }
