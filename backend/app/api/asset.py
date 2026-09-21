"""Per-asset price + history endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_optional
from app.models.user import User
from app.services.market import CoinGeckoService, YahooFinanceService
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api", tags=["asset"])
_yahoo = YahooFinanceService()
_coingecko = CoinGeckoService()


async def _resolve_asset_type(ticker: str, current_user: User | None, asset_type: str) -> str:
    if asset_type != "auto":
        return asset_type
    if current_user is not None:
        positions = await PortfolioService(current_user.id).load_positions()
        pos = positions[positions["ticker"].str.upper() == ticker.upper()]
    else:
        import pandas as pd
        pos = pd.DataFrame()
    if not pos.empty:
        return pos.iloc[0]["type"]
    if ticker.upper() in {"BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA"}:
        return "crypto"
    return "stock"


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
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    asset_type = await _resolve_asset_type(ticker, current_user, asset_type)

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
        # True only when the rows actually carry a unix-timestamp "time" field
        # (real intraday candles) — checked on the data itself, not just the
        # requested period, since a crypto fallback to CoinGecko never has it.
        "intraday": bool(history) and "time" in history[0],
    }


@router.get("/asset/{ticker}/stats")
async def get_asset_stats(
    ticker: str,
    asset_type: str = Query(default="auto"),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    """Quick-stats strip for the asset chart pages: day range, 52-week range,
    average volume, market cap, PER, dividend yield, next earnings/ex-dividend,
    insider sentiment. Every field is best-effort — missing ones are simply
    omitted, never fabricated."""
    asset_type = await _resolve_asset_type(ticker, current_user, asset_type)
    lookup_ticker = f"{ticker.upper()}-EUR" if asset_type == "crypto" else ticker

    out: dict = {}
    fast = await _yahoo.get_fast_stats(lookup_ticker)
    if fast:
        out.update(fast)

    descr = await _yahoo.get_description(lookup_ticker)
    if descr:
        out["description"] = descr

    if asset_type != "crypto":
        fund = await _yahoo.get_fundamentals(ticker)
        if fund:
            if fund.get("trailingPE") is not None:
                out["pe_ratio"] = fund["trailingPE"]
            if fund.get("dividendYield") is not None:
                out["dividend_yield"] = fund["dividendYield"]
            if out.get("market_cap") is None and fund.get("marketCap") is not None:
                out["market_cap"] = fund["marketCap"]

        cats = await _yahoo.get_catalysts(ticker)
        if cats:
            if cats.get("earnings"):
                out["next_earnings"] = cats["earnings"]
            if cats.get("ex_dividend"):
                out["next_ex_dividend"] = cats["ex_dividend"]

        from app.services.market.finnhub import FinnhubClient
        insider = await FinnhubClient().get_insider_sentiment(ticker)
        if insider:
            out["insider_mspr"] = insider.get("mspr")
            out["insider_month"] = insider.get("month")

    # Same benchmark the engine itself uses for beta/alpha (asset_analysis.py),
    # so "vs índice" on the chart matches what the deep-analysis modal compares
    # against — not a second, inconsistent notion of "the market".
    from app.services.asset_analysis import _benchmark_for
    bfor_ticker = f"{ticker.upper()}-USD" if asset_type == "crypto" else ticker
    bench_category = "cripto" if asset_type == "crypto" else ""
    bench_ticker, bench_name = _benchmark_for(bfor_ticker, category=bench_category)
    if bench_ticker.upper() != ticker.upper():
        out["benchmark_ticker"] = bench_ticker
        out["benchmark_name"] = bench_name

    return out
