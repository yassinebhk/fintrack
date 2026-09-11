"""Automatic daily day-trade picker.

Converts one high-conviction idea from today's already-computed opportunities
scan (app.services.opportunities, the same quant screener that feeds the
medium/long-term daily briefing) into a paper Trading Diario entry.
Deliberately conservative, consistent with the project's anti-noise
philosophy (app.services.scorecard, app.services.systematic.paper): the
quant signals decide which tickers are even in the running; real news is
used only to VETO a specific candidate or raise the bar on a bearish macro
day — never to invent a reason to trade a name the quant score didn't
already support. Most days should open ZERO trades — that's a feature.

Two real-news checks (both via app.services.news.NewsService, the same RSS
aggregator — Bloomberg/CNBC/Reuters/FT/etc. — already used by the daily
briefing and the medium/long-term opportunities LLM step):

  1. Per-candidate veto: a concrete, recent, specific bearish headline about
     THAT ticker (earnings miss, lawsuit, downgrade...) disqualifies it, even
     if the technicals look good. A positive/neutral tape does not add
     conviction beyond what the quant score already gives it — good news
     doesn't override a candidate that failed the quant bar.
  2. Macro caution: if most of today's recent economy/politics headlines are
     bearish, marginal candidates (barely over the quant thresholds) are
     skipped — only a clearer edge survives a jittery macro backdrop. This
     never LOWERS the bar on a calm/bullish day, only raises it on a bad one.

Only reads the already-cached opportunities payload (never triggers a new
scan itself); only considers `themes` (single stocks/ETFs), not crypto; only
opens longs; caps at one new trade per run so the daily journal stays a
readable, statistically clean sample rather than a firehose.
"""

from __future__ import annotations

from loguru import logger

from app.services.daytrading import journal
from app.services.news import NewsService
from app.services.opportunities import get_opportunity_service

STAKE_EUR = 100.0
STOP_LOSS_PCT = 3.0
TAKE_PROFIT_PCT = 6.0

MIN_MOMENTUM_SCORE = 1.5
MIN_SHARPE = 1.5
RSI_MIN = 35.0
RSI_MAX = 70.0  # avoid chasing an already-overbought move

MACRO_BEARISH_RATIO = 0.6   # >=60% of recent economy/politics headlines bearish -> get cautious
MACRO_MOMENTUM_MARGIN = 1.3  # on a cautious day, require this much extra momentum margin
NEWS_LOOKBACK = 8            # most recent ticker-specific headlines to inspect

_news = NewsService()


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


async def _macro_caution() -> dict:
    """Real macro backdrop: % of recent economy/politics headlines that are
    bearish right now. Used only to raise the bar — never to lower it."""
    try:
        economy = await _news.get_news("economy", limit=15)
        politics = await _news.get_news("politics", limit=10)
    except Exception as exc:
        logger.debug("day trading auto-pick: macro news fetch failed: {}", exc)
        return {"bearish_ratio": 0.0, "n": 0}
    macro_news = economy + politics
    if not macro_news:
        return {"bearish_ratio": 0.0, "n": 0}
    bearish = sum(1 for n in macro_news if n.get("impact") == "bearish")
    return {"bearish_ratio": bearish / len(macro_news), "n": len(macro_news)}


async def _ticker_news_check(ticker: str) -> dict:
    """Recent real headlines specifically about this ticker. A concrete
    bearish one vetoes the trade; anything else is informational only."""
    try:
        items = await _news.get_news_for_asset(ticker, limit=NEWS_LOOKBACK)
    except Exception as exc:
        logger.debug("day trading auto-pick: news fetch failed for {}: {}", ticker, exc)
        return {"items": [], "veto": False, "bearish": []}
    bearish = [n for n in items if n.get("impact") == "bearish"]
    return {"items": items, "veto": bool(bearish), "bearish": bearish}


def _thesis(theme: dict, news_items: list[dict], macro: dict) -> str:
    signals = theme.get("signals") or {}
    factors = theme.get("factors") or {}
    parts = [
        f"Auto (motor cuantitativo diario): momentum {theme.get('momentum_score'):.2f}, "
        f"Sharpe {factors.get('sharpe'):.2f}, RSI {signals.get('rsi'):.0f}, "
        f"tendencia y MACD alcistas, precio > SMA200."
    ]
    if news_items:
        top = news_items[0]
        parts.append(f'Noticia reciente ({top["source"]}): "{top["title"]}" [{top["impact"]}].')
    if macro["n"]:
        parts.append(
            f"Contexto macro: {macro['bearish_ratio'] * 100:.0f}% de {macro['n']} "
            f"titulares económicos/políticos recientes son bajistas."
        )
    return " ".join(parts)


async def pick_and_open(user_id: int) -> dict:
    """Look at today's cached opportunities; open at most ONE new long paper
    trade for the best-qualifying idea that also survives the real-news veto
    and macro-caution check. Skips entirely (opened=None) if nothing clears
    every bar, or every remaining candidate already has an open position."""
    payload = await get_opportunity_service().peek_or_start(force=False)
    themes = payload.get("themes") or []
    if not themes:
        return {"opened": None, "reason": "no opportunities cached yet"}

    open_trades = await journal.list_trades(user_id, status="open")
    open_tickers = {t["ticker"] for t in open_trades}

    candidates = sorted(
        (t for t in themes if _qualifies(t) and t.get("ticker") not in open_tickers),
        key=lambda t: t.get("momentum_score") or 0,
        reverse=True,
    )
    if not candidates:
        return {"opened": None, "reason": "no candidate cleared the bar today"}

    macro = await _macro_caution()
    cautious = macro["bearish_ratio"] >= MACRO_BEARISH_RATIO
    if cautious:
        logger.info(
            "day trading auto-pick: cautious macro tape ({:.0%} of {} bearish) — requiring extra momentum margin",
            macro["bearish_ratio"], macro["n"],
        )

    for theme in candidates:
        ticker = theme["ticker"]
        if cautious and (theme.get("momentum_score") or 0) < MIN_MOMENTUM_SCORE * MACRO_MOMENTUM_MARGIN:
            logger.info("day trading auto-pick: skipping {} — doesn't clear the cautious-day bar", ticker)
            continue
        news = await _ticker_news_check(ticker)
        if news["veto"]:
            logger.info(
                "day trading auto-pick: skipping {} — recent bearish headline: {}",
                ticker, news["bearish"][0]["title"],
            )
            continue
        try:
            trade = await journal.open_trade(
                user_id=user_id,
                ticker=ticker,
                direction="long",
                thesis=_thesis(theme, news["items"], macro),
                stake_eur=STAKE_EUR,
                stop_loss_pct=STOP_LOSS_PCT,
                take_profit_pct=TAKE_PROFIT_PCT,
                conviction="alta",
                name=theme.get("theme", ticker),
            )
            logger.info("day trading auto-pick: opened {} ({})", ticker, trade.get("id"))
            return {"opened": trade, "macro": macro}
        except Exception as exc:
            logger.error("day trading auto-pick: failed to open {}: {}", ticker, exc)
            continue

    return {"opened": None, "reason": "all candidates vetoed by news or macro caution", "macro": macro}
