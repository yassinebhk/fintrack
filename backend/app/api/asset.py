"""Per-asset price + history endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.services.market import CoinGeckoService, YahooFinanceService
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api", tags=["asset"])
_portfolio = PortfolioService()
_yahoo = YahooFinanceService()
_coingecko = CoinGeckoService()


@router.get("/price/{ticker}")
async def get_price(ticker: str, asset_type: str = Query(default="stock")) -> dict:
    if asset_type == "crypto":
        price = await _coingecko.get_price(ticker, vs_currency="eur")
        if price is None:
            # CoinGecko free tier rate-limits aggressively — fall back to Yahoo BTC-EUR style
            price = await _yahoo.get_price(f"{ticker.upper()}-EUR")
    else:
        price = await _yahoo.get_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Price not found for {ticker}")
    return price


@router.get("/asset/{ticker}/history")
async def get_asset_history(
    ticker: str,
    period: str = Query(default="1y", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    asset_type: str = Query(default="auto"),
) -> dict:
    if asset_type == "auto":
        positions = await _portfolio.load_positions()
        pos = positions[positions["ticker"].str.upper() == ticker.upper()]
        if not pos.empty:
            asset_type = pos.iloc[0]["type"]
        elif ticker.upper() in {"BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA"}:
            asset_type = "crypto"
        else:
            asset_type = "stock"

    if asset_type == "crypto":
        # Yahoo first: it has real OHLC (candles actually render) and no rate
        # limit. CoinGecko's free tier 429s constantly and get_history() blocks
        # for a 60s retry-sleep on a hit, which used to make this endpoint hang
        # for a minute — only fall back to it for coins Yahoo doesn't track.
        yahoo_ticker = f"{ticker.upper()}-EUR"
        history = await _yahoo.get_history(yahoo_ticker, period=period)
        current = await _yahoo.get_price(yahoo_ticker)
        if not history:
            period_days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 2000}
            days = period_days.get(period, 365)
            history = await _coingecko.get_history(ticker, days=days, vs_currency="eur")
        if current is None:
            current = await _coingecko.get_price(ticker, vs_currency="eur")
    else:
        history = await _yahoo.get_history(ticker, period=period)
        current = await _yahoo.get_price(ticker)

    if not history:
        raise HTTPException(status_code=404, detail=f"No historical data for {ticker}")
    return {
        "ticker": ticker.upper(),
        "type": asset_type,
        "period": period,
        "history": history,
        "current": current,
        "data_points": len(history),
    }
