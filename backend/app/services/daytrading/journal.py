"""Day-trading paper journal: open/close discretionary trades, mark them to
market, and compute an honest, gated verdict on whether the activity beats a
passive benchmark — using the same anti-noise philosophy as
app.services.scorecard and app.services.systematic.paper.

Nothing here moves real money. Every trade needs a written thesis (>=20 chars)
and a stop-loss before it can be opened.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from loguru import logger
from scipy.stats import ttest_1samp

from app.db import session_scope
from app.models.day_trade import DayTrade
from app.repositories.day_trades import DayTradeRepository
from app.services.market import CoinGeckoService, YahooFinanceService

MIN_N_TRADES = 30          # same floor as MIN_N_FEEDBACK in scorecard.py
MIN_SPAN_DAYS = 60         # ~2 months, what was promised to the user
MAX_HOLD_DAYS = 30         # auto time-exit so a losing trade isn't held forever
_BENCHMARK = "EUNL.DE"     # same benchmark as systematic/paper.py
MIN_THESIS_CHARS = 20

_CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA"}

_yahoo = YahooFinanceService()
_coingecko = CoinGeckoService()


async def _current_price(ticker: str) -> float | None:
    up = ticker.upper()
    if up in _CRYPTO_TICKERS:
        p = await _coingecko.get_price(up, vs_currency="eur")
        if p is None:
            p = await _yahoo.get_price(f"{up}-EUR")
        return p.get("price") if p else None
    p = await _yahoo.get_price(up)
    return p.get("price") if p else None


def serialize(trade: DayTrade, live_price: float | None = None) -> dict:
    unrealized_pct = None
    if trade.status == "open" and live_price:
        if trade.direction == "long":
            unrealized_pct = (live_price - trade.entry_price) / trade.entry_price * 100
        else:
            unrealized_pct = (trade.entry_price - live_price) / trade.entry_price * 100
    return {
        "id": trade.id,
        "opened_at": trade.opened_at.isoformat() if trade.opened_at else None,
        "ticker": trade.ticker,
        "name": trade.name,
        "direction": trade.direction,
        "conviction": trade.conviction,
        "thesis": trade.thesis,
        "news_url": trade.news_url,
        "stake_eur": trade.stake_eur,
        "entry_price": trade.entry_price,
        "quantity": trade.quantity,
        "stop_loss": trade.stop_loss,
        "take_profit": trade.take_profit,
        "status": trade.status,
        "close_reason": trade.close_reason,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        "exit_price": trade.exit_price,
        "pnl_eur": trade.pnl_eur,
        "pnl_pct": trade.pnl_pct,
        "bench_pnl_pct": trade.bench_pnl_pct,
        "live_price": live_price,
        "unrealized_pnl_pct": round(unrealized_pct, 2) if unrealized_pct is not None else None,
    }


async def open_trade(
    ticker: str,
    direction: str,
    thesis: str,
    stake_eur: float,
    stop_loss_pct: float,
    conviction: str = "media",
    take_profit_pct: float | None = None,
    news_url: str | None = None,
    name: str = "",
) -> dict:
    """Open a new paper trade. Raises ValueError on missing thesis/stop-loss —
    the API layer turns that into a 400, not a silent default."""
    thesis = (thesis or "").strip()
    if len(thesis) < MIN_THESIS_CHARS:
        raise ValueError(f"La tesis debe tener al menos {MIN_THESIS_CHARS} caracteres, escrita ANTES de abrir la operación.")
    if direction not in ("long", "short"):
        raise ValueError("direction debe ser 'long' o 'short'")
    if not stop_loss_pct or stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct es obligatorio y debe ser > 0")
    if stake_eur <= 0:
        raise ValueError("stake_eur debe ser > 0")

    up = ticker.upper().strip()
    price = await _current_price(up)
    if not price or price <= 0:
        raise ValueError(f"No se pudo obtener un precio de mercado fiable para {up}")

    if direction == "long":
        stop_loss = price * (1 - stop_loss_pct / 100)
        take_profit = price * (1 + take_profit_pct / 100) if take_profit_pct else None
    else:
        stop_loss = price * (1 + stop_loss_pct / 100)
        take_profit = price * (1 - take_profit_pct / 100) if take_profit_pct else None

    bench_price = await _current_price(_BENCHMARK)
    quantity = stake_eur / price

    async with session_scope() as session:
        repo = DayTradeRepository(session)
        trade = await repo.add(
            ticker=up,
            name=name,
            direction=direction,
            conviction=conviction,
            thesis=thesis,
            news_url=news_url,
            stake_eur=stake_eur,
            entry_price=price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            benchmark_ticker=_BENCHMARK,
            bench_price_at_open=bench_price,
            status="open",
        )
    return serialize(trade)


def _pnl(trade: DayTrade, exit_price: float) -> tuple[float, float]:
    if trade.direction == "long":
        pnl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
    else:
        pnl_pct = (trade.entry_price - exit_price) / trade.entry_price * 100
    pnl_eur = trade.stake_eur * pnl_pct / 100
    return pnl_eur, pnl_pct


async def close_trade(trade_id: int, reason: str = "manual") -> dict | None:
    async with session_scope() as session:
        repo = DayTradeRepository(session)
        trade = await repo.get(trade_id)
        if trade is None or trade.status != "open":
            return None
        price = await _current_price(trade.ticker)
        if not price or price <= 0:
            raise ValueError(f"No se pudo obtener precio actual de {trade.ticker} para cerrar")
        pnl_eur, pnl_pct = _pnl(trade, price)

        bench_pnl_pct = None
        bench_price = await _current_price(trade.benchmark_ticker)
        if bench_price and trade.bench_price_at_open:
            bench_pnl_pct = (bench_price - trade.bench_price_at_open) / trade.bench_price_at_open * 100

        updated = await repo.close(
            trade_id,
            close_reason=reason,
            exit_price=price,
            bench_price_at_close=bench_price,
            pnl_eur=round(pnl_eur, 2),
            pnl_pct=round(pnl_pct, 2),
            bench_pnl_pct=round(bench_pnl_pct, 2) if bench_pnl_pct is not None else None,
        )
        return serialize(updated) if updated is not None else None


async def mark_open_trades() -> dict:
    """Daily job: close any open trade whose stop-loss, take-profit, or max hold
    time has been hit. Never lets one bad price fetch kill the whole run."""
    closed = []
    async with session_scope() as session:
        repo = DayTradeRepository(session)
        open_trades = await repo.list_open()

    now = datetime.now(timezone.utc)
    for trade in open_trades:
        try:
            price = await _current_price(trade.ticker)
            if not price:
                continue
            reason = None
            if trade.direction == "long":
                if price <= trade.stop_loss:
                    reason = "stop_loss"
                elif trade.take_profit and price >= trade.take_profit:
                    reason = "take_profit"
            else:
                if price >= trade.stop_loss:
                    reason = "stop_loss"
                elif trade.take_profit and price <= trade.take_profit:
                    reason = "take_profit"
            opened_at = trade.opened_at
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            if reason is None and (now - opened_at) > timedelta(days=MAX_HOLD_DAYS):
                reason = "time_exit"
            if reason:
                await close_trade(trade.id, reason=reason)
                closed.append({"id": trade.id, "ticker": trade.ticker, "reason": reason})
        except Exception as exc:
            logger.debug("day trading mark: {} failed: {}", trade.ticker, exc)
    return {"checked": len(open_trades), "closed": closed}


async def list_trades(status: str = "all") -> list[dict]:
    async with session_scope() as session:
        repo = DayTradeRepository(session)
        if status == "open":
            trades = await repo.list_open()
        elif status == "closed":
            trades = await repo.list_closed()
        else:
            trades = await repo.list_all()

    live_prices: dict[int, float | None] = {}
    for trade in trades:
        if trade.status == "open":
            try:
                live_prices[trade.id] = await _current_price(trade.ticker)
            except Exception:
                live_prices[trade.id] = None
    return [serialize(t, live_prices.get(t.id)) for t in trades]


async def report() -> dict:
    async with session_scope() as session:
        repo = DayTradeRepository(session)
        closed = await repo.list_closed()
        open_trades = await repo.list_open()

    n = len(closed)
    if n == 0:
        return {
            "n_closed": 0,
            "n_open": len(open_trades),
            "status": "sin operaciones cerradas todavía",
            "readiness": {"ready": False, "verdict": f"NO apto — sigue en papel (0/{MIN_N_TRADES} operaciones)"},
        }

    pnls = [t.pnl_pct for t in closed if t.pnl_pct is not None]
    bench_pnls = [t.bench_pnl_pct for t in closed if t.bench_pnl_pct is not None]
    dates = [t.closed_at for t in closed if t.closed_at is not None]
    span_days = (max(dates) - min(dates)).days if len(dates) > 1 else 0

    hit_rate_pct = round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 1) if pnls else None
    mean_pnl_pct = round(mean(pnls), 2) if pnls else None
    mean_bench_pnl_pct = round(mean(bench_pnls), 2) if bench_pnls else None
    worst_pct = round(min(pnls), 2) if pnls else None

    p_value = None
    if len(pnls) >= 5:
        try:
            p_value = round(float(ttest_1samp(pnls, 0.0).pvalue), 3)
        except Exception as exc:
            logger.debug("day trading report: t-test failed: {}", exc)

    total_pnl_eur = round(sum(t.pnl_eur for t in closed if t.pnl_eur is not None), 2)

    out = {
        "n_closed": n,
        "n_open": len(open_trades),
        "span_days": span_days,
        "hit_rate_pct": hit_rate_pct,
        "mean_pnl_pct": mean_pnl_pct,
        "mean_benchmark_pnl_pct": mean_bench_pnl_pct,
        "alpha_pct": round(mean_pnl_pct - mean_bench_pnl_pct, 2) if (mean_pnl_pct is not None and mean_bench_pnl_pct is not None) else None,
        "worst_trade_pct": worst_pct,
        "p_value": p_value,
        "total_pnl_eur": total_pnl_eur,
    }
    out["readiness"] = _readiness(out)
    return out


def _readiness(r: dict) -> dict:
    n = r["n_closed"]
    span = r["span_days"]
    checks = {
        "sample_ok": n >= MIN_N_TRADES and span >= MIN_SPAN_DAYS,
        "beats_benchmark": (
            r["alpha_pct"] is not None and r["alpha_pct"] > 0
        ),
        "significant": r["p_value"] is not None and r["p_value"] < 0.10,
        "no_blowup": r["worst_trade_pct"] is None or r["worst_trade_pct"] > -50,
    }
    ready = all(checks.values())
    return {
        **checks,
        "ready": ready,
        "verdict": (
            "Datos suficientes y consistentes — decisión de meter dinero real es tuya, nunca automática"
            if ready
            else f"NO apto — sigue en papel ({n}/{MIN_N_TRADES} operaciones, {span}/{MIN_SPAN_DAYS} días)"
        ),
    }
