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


@router.post("/portfolio-card")
async def portfolio_card(secret: str = "") -> dict:
    """Render the portfolio as a pretty image (today's % per holding) and send it
    to Telegram as a photo, with a headline caption. Excludes the user's dust list."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    from app.services.charts import portfolio_today_chart
    from app.services.notifications.telegram import TelegramNotifier
    from app.services.portfolio import PortfolioService
    from app.services.report_prefs import get_excluded

    p = await PortfolioService().calculate_portfolio()
    excluded = await get_excluded()
    positions = [x for x in p.get("positions", []) if (x.get("ticker") or "").upper() not in excluded]
    if not positions:
        raise HTTPException(status_code=404, detail="sin posiciones")

    def _to_base(pos: dict, field: str) -> float:
        mv = pos.get("market_value") or 0
        fx = (pos["market_value_base"] / mv) if mv else 1.0
        return (pos.get(field) or 0) * fx

    cur = p.get("base_currency", "EUR")
    total = sum(x.get("market_value_base", 0) for x in positions)
    cost = sum(_to_base(x, "cost_basis") for x in positions)
    daily = sum(_to_base(x, "day_change") for x in positions)
    pl = total - cost
    pl_pct = (pl / cost * 100) if cost > 0 else 0.0
    daily_pct = (daily / (total - daily) * 100) if (total - daily) > 0 else 0.0

    rows = sorted(positions, key=lambda x: (x.get("day_change_pct") or 0), reverse=True)[:12]
    labels, values = [], []
    for x in rows:
        nm = (x.get("name") or x["ticker"]).replace("&", "y")[:14]
        d = x.get("day_change_pct") or 0
        labels.append(f"{nm} {d:+.1f}%")
        values.append(round(d, 2))
    title_lines = [
        f"Cartera {total:.0f} {cur}",
        f"Hoy {daily:+.0f} {cur} ({daily_pct:+.1f}%)  -  P/L {pl_pct:+.1f}%",
    ]
    url = portfolio_today_chart(title_lines, labels, values)
    caption = (f"💼 <b>Tu cartera</b> · {total:.2f} {cur}\n"
               f"{'📈' if daily >= 0 else '📉'} Hoy: {daily:+.2f} {cur} ({daily_pct:+.2f}%)\n"
               f"💰 P/L total: {pl:+.2f} {cur} ({pl_pct:+.2f}%)")
    if excluded:
        caption += f"\n<i>excl.: {', '.join(sorted(excluded))}</i>"
    ok = await TelegramNotifier().send_photo(url, caption=caption[:1024])
    return {"sent": bool(ok), "positions": len(rows)}


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
