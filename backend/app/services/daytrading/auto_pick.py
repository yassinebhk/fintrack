"""Automatic daily day-trade picker.

Converts the single highest-conviction idea from today's already-computed
opportunities scan (app.services.opportunities, the same quant screener that
feeds the medium/long-term daily briefing) into one paper Trading Diario
entry. Deliberately conservative, consistent with the project's anti-noise
philosophy (app.services.scorecard, app.services.systematic.paper): the
quant signals decide, nothing here goes hunting for a reason to trade. Most
days should open ZERO trades — that's a feature, not a bug.

Only reads the already-cached opportunities payload (never triggers a new
scan itself); only considers `themes` (single stocks/ETFs), not crypto; only
opens longs; caps at one new trade per run so the daily journal stays a
readable, statistically clean sample rather than a firehose.
"""

from __future__ import annotations

from loguru import logger

from app.services.daytrading import journal
from app.services.opportunities import get_opportunity_service

STAKE_EUR = 100.0
STOP_LOSS_PCT = 3.0
TAKE_PROFIT_PCT = 6.0

MIN_MOMENTUM_SCORE = 1.5
MIN_SHARPE = 1.5
RSI_MIN = 35.0
RSI_MAX = 70.0  # avoid chasing an already-overbought move


def _qualifies(theme: dict) -> bool:
    signals = theme.get("signals") or {}
    factors = theme.get("factors") or {}
    rsi = signals.get("rsi")
    if rsi is None or not (RSI_MIN <= rsi <= RSI_MAX):
        return False
    if signals.get("trend") != "alcista" or signals.get("macd_signal") != "alcista":
        return False
    if not signals.get("above_sma200"):
        return False
    if (theme.get("momentum_score") or 0) < MIN_MOMENTUM_SCORE:
        return False
    if (factors.get("sharpe") or 0) < MIN_SHARPE:
        return False
    return True


def _thesis(theme: dict) -> str:
    signals = theme.get("signals") or {}
    factors = theme.get("factors") or {}
    return (
        f"Auto (motor cuantitativo diario): momentum {theme.get('momentum_score'):.2f}, "
        f"Sharpe {factors.get('sharpe'):.2f}, RSI {signals.get('rsi'):.0f}, "
        f"tendencia y MACD alcistas, precio > SMA200."
    )


async def pick_and_open() -> dict:
    """Look at today's cached opportunities; open at most ONE new long paper
    trade for the single best-qualifying idea. Skips entirely (returns
    opened=None) if nothing clears the bar or the best candidate already has
    an open position."""
    payload = await get_opportunity_service().peek_or_start(force=False)
    themes = payload.get("themes") or []
    if not themes:
        return {"opened": None, "reason": "no opportunities cached yet"}

    open_trades = await journal.list_trades(status="open")
    open_tickers = {t["ticker"] for t in open_trades}

    candidates = [
        t for t in themes
        if _qualifies(t) and t.get("ticker") not in open_tickers
    ]
    if not candidates:
        return {"opened": None, "reason": "no candidate cleared the bar today"}

    best = max(candidates, key=lambda t: t.get("momentum_score") or 0)
    ticker = best["ticker"]
    try:
        trade = await journal.open_trade(
            ticker=ticker,
            direction="long",
            thesis=_thesis(best),
            stake_eur=STAKE_EUR,
            stop_loss_pct=STOP_LOSS_PCT,
            take_profit_pct=TAKE_PROFIT_PCT,
            conviction="alta",
            name=best.get("theme", ticker),
        )
        logger.info("day trading auto-pick: opened {} ({})", ticker, trade.get("id"))
        return {"opened": trade}
    except Exception as exc:
        logger.error("day trading auto-pick: failed to open {}: {}", ticker, exc)
        return {"opened": None, "reason": str(exc)}
