"""News endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.services.news import NewsService

router = APIRouter(prefix="/api/news", tags=["news"])
_service = NewsService()


@router.get("")
async def get_news(
    category: str = Query(default="all"),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    news = await _service.get_news(category=category, limit=limit)
    return {
        "news": news,
        "count": len(news),
        "category": category,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/asset/{ticker}")
async def get_news_for_asset(ticker: str, limit: int = Query(default=10, ge=1, le=50)) -> dict:
    news = await _service.get_news_for_asset(ticker=ticker, limit=limit)
    return {"ticker": ticker.upper(), "news": news, "count": len(news)}
