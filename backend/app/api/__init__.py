"""HTTP routers registered into the FastAPI app."""

from fastapi import APIRouter

from app.api import (
    ai,
    alerts,
    asset,
    backtest,
    briefings,
    brokers,
    fx,
    health,
    imports,
    news,
    polymarket,
    portfolio,
    positions,
    transactions,
)


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(portfolio.router)
    router.include_router(positions.router)
    router.include_router(transactions.router)
    router.include_router(asset.router)
    router.include_router(fx.router)
    router.include_router(news.router)
    router.include_router(ai.router)
    router.include_router(imports.router)
    router.include_router(brokers.router)
    router.include_router(briefings.router)
    router.include_router(alerts.router)
    router.include_router(backtest.router)
    router.include_router(polymarket.router)
    return router
