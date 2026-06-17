"""Secret-gated endpoint to push an arbitrary HTML message to the configured Telegram chat."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/notify", tags=["notify"])
_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


class NotifyIn(BaseModel):
    html: str = Field(min_length=1)


@router.post("/send")
async def send(payload: NotifyIn, secret: str = "") -> dict:
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    try:
        from app.services.notifications.telegram import TelegramNotifier
        ok = await TelegramNotifier().send_html(payload.html[:4000])
        return {"sent": bool(ok)}
    except Exception as exc:
        logger.exception("notify send failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _send_portfolio_table() -> None:
    from app.services.notifications.telegram import TelegramNotifier
    from app.services.portfolio import PortfolioService
    from app.services.portfolio_report import build_summary_html
    from app.services.report_prefs import get_excluded
    try:
        p = await PortfolioService().calculate_portfolio()
        excluded = await get_excluded()
        await TelegramNotifier().send_html(build_summary_html(p, excluded))
    except Exception:
        logger.exception("portfolio-card send failed")


@router.post("/portfolio-card")
async def portfolio_card(secret: str = "") -> dict:
    """Send the portfolio to Telegram as a clean monospace table (headline + grid).
    Runs in the background so the heavy live-price recompute never hits the gateway
    timeout (Render free tier)."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    import asyncio
    asyncio.create_task(_send_portfolio_table())
    return {"status": "accepted"}


class ChartReq(BaseModel):
    ticker: str
    label: str = ""
    period: str = "6mo"


class ChartsIn(BaseModel):
    items: list[ChartReq]


@router.post("/charts")
async def charts(payload: ChartsIn, secret: str = "") -> dict:
    """Build a price chart per ticker and send it to Telegram as a photo."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    from app.services.charts import line_chart
    from app.services.discovery.market_scanner import MarketScanner
    from app.services.notifications.telegram import TelegramNotifier

    scanner = MarketScanner()
    notifier = TelegramNotifier()
    sent, failed = [], []
    for it in payload.items:
        try:
            hist = await scanner.yahoo.get_history(it.ticker, period=it.period)
            closes = [h["close"] for h in (hist or []) if h.get("close")]
            labels = [h["date"] for h in (hist or []) if h.get("close")]
            if len(closes) < 20:
                failed.append(it.ticker)
                continue
            up = closes[-1] >= closes[0]
            chg = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
            color = "#10b981" if up else "#ef4444"
            name = it.label or it.ticker
            url = line_chart(f"{name} · {it.period}"[:60], labels, closes, color=color)
            caption = f"📈 <b>{name}</b> ({it.ticker}) · {it.period}: {chg:+.1f}% · último {closes[-1]:.2f}"
            ok = await notifier.send_photo(url, caption=caption)
            (sent if ok else failed).append(it.ticker)
        except Exception as exc:
            logger.warning("notify chart {} failed: {}", it.ticker, exc)
            failed.append(it.ticker)
    return {"sent": sent, "failed": failed}
