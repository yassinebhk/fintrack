"""HTTP routers registered into the FastAPI app."""

from fastapi import APIRouter

from app.api import (
    ai,
    alerts,
    asset,
    assets,
    backtest,
    briefings,
    brokers,
    creators,
    fx,
    health,
    imports,
    news,
    notify,
    opportunities,
    plans,
    polymarket,
    portfolio,
    position_review,
    positions,
    scorecard,
    settings,
    telegram,
    transactions,
)


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(portfolio.router)
    router.include_router(positions.router)
    router.include_router(position_review.router)
    router.include_router(transactions.router)
    router.include_router(asset.router)
    router.include_router(assets.router)
    router.include_router(fx.router)
    router.include_router(news.router)
    router.include_router(notify.router)
    router.include_router(ai.router)
    router.include_router(imports.router)
    router.include_router(brokers.router)
    router.include_router(briefings.router)
    router.include_router(alerts.router)
    router.include_router(backtest.router)
    router.include_router(creators.router)
    router.include_router(polymarket.router)
    router.include_router(opportunities.router)
    router.include_router(plans.router)
    router.include_router(scorecard.router)
    router.include_router(settings.router)
    router.include_router(telegram.router)
    return router
