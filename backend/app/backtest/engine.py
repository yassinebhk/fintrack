"""Backtest engine — converts strategy trade signals into an equity curve + metrics."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from app.backtest.strategies import STRATEGIES, get_strategy
from app.backtest.validation import purged_walk_forward, sharpe_metrics
from app.services.market import CoinGeckoService, YahooFinanceService


@dataclass
class BacktestSpec:
    strategy_key: str
    tickers: list[str]
    asset_types: dict[str, str]  # ticker -> 'crypto' | 'stock' | 'etf'
    start_date: str  # YYYY-MM-DD
    end_date: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    strategy_key: str
    tickers: list[str]
    start_date: str
    end_date: str
    equity_curve: list[dict]  # [{date, value}]
    trades: list[dict]
    metrics: dict[str, Any]


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

async def _fetch_price_history(
    tickers: list[str],
    asset_types: dict[str, str],
    start: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch close prices for tickers from start → today. Returns wide DataFrame indexed by date."""
    yahoo = YahooFinanceService()
    coingecko = CoinGeckoService()

    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    start_naive = start.tz_localize(None) if start.tz is not None else start
    days_back = max((today - start_naive).days, 30)

    async def fetch_one(ticker: str) -> pd.Series:
        atype = asset_types.get(ticker, "stock")
        try:
            if atype == "crypto":
                # CoinGecko free tier caps history at ~365 days; fall back to yfinance with -EUR suffix for longer ranges
                if days_back > 350:
                    yahoo_ticker = f"{ticker}-EUR"
                    period = "max" if days_back > 1825 else "5y" if days_back > 730 else "2y"
                    logger.info("crypto {} > 350d → using yfinance {}", ticker, yahoo_ticker)
                    hist = await yahoo.get_history(yahoo_ticker, period=period)
                else:
                    hist = await coingecko.get_history(ticker, days=days_back, vs_currency="eur")
            else:
                period = "max" if days_back > 1825 else "5y" if days_back > 730 else "2y" if days_back > 365 else "1y" if days_back > 90 else "3mo"
                hist = await yahoo.get_history(ticker, period=period)
        except Exception as exc:
            logger.warning("history fetch failed for {}: {}", ticker, exc)
            return pd.Series(dtype=float, name=ticker)
        if not hist:
            return pd.Series(dtype=float, name=ticker)
        df = pd.DataFrame(hist)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df["close"].rename(ticker)

    series_list = await asyncio.gather(*(fetch_one(t) for t in tickers))
    if not series_list:
        return pd.DataFrame()
    combined = pd.concat(series_list, axis=1)
    combined = combined.sort_index().ffill().dropna(how="all")
    combined = combined[combined.index >= start]
    return combined


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def _simulate(prices: pd.DataFrame, trades: pd.DataFrame, weights: dict[str, float]) -> tuple[pd.Series, list[dict]]:
    """Apply trades to a simulated portfolio. Returns equity series + executed-trades list.

    Model: each "buy" is interpreted as a fresh contribution from the user — the
    money to buy comes from outside the portfolio, not from internal cash. So
    `cash` only tracks proceeds from sells that haven't been reinvested.
    equity = cash + sum(holdings * price).
    """
    if trades is None or trades.empty:
        return pd.Series(dtype=float, name="equity"), []

    holdings: dict[str, float] = {t: 0.0 for t in prices.columns}
    cash = 0.0  # only sell proceeds live here
    executed: list[dict] = []

    # Index trades by date
    trades_by_date: dict[pd.Timestamp, list[dict]] = {}
    for _, row in trades.iterrows():
        d = pd.Timestamp(row["date"])
        idx = prices.index.searchsorted(d)
        if idx >= len(prices.index):
            continue
        d_snap = prices.index[idx]
        trades_by_date.setdefault(d_snap, []).append(row.to_dict())

    equity_records: list[tuple[pd.Timestamp, float]] = []
    for d in prices.index:
        if d in trades_by_date:
            for tr in trades_by_date[d]:
                action = tr["action"]
                ticker = tr["ticker"]
                amt = float(tr.get("amount_eur") or 0)

                if action == "buy" and ticker in prices.columns:
                    price = float(prices.loc[d, ticker])
                    if price and price > 0:
                        # Use cash from prior sells first, rest is external contribution
                        from_cash = min(cash, amt) if cash > 0 else 0.0
                        cash -= from_cash
                        shares = amt / price
                        holdings[ticker] = holdings.get(ticker, 0.0) + shares
                        executed.append({
                            "date": d.strftime("%Y-%m-%d"),
                            "ticker": ticker,
                            "action": "buy",
                            "amount_eur": round(amt, 2),
                            "contribution_eur": round(amt - from_cash, 2),
                            "price": round(price, 6),
                            "shares": round(shares, 8),
                        })
                elif action == "sell" and ticker in prices.columns:
                    price = float(prices.loc[d, ticker])
                    if price and price > 0:
                        max_shares = holdings.get(ticker, 0.0)
                        target_shares = amt / price
                        shares = min(max_shares, target_shares)
                        holdings[ticker] -= shares
                        proceeds = shares * price
                        cash += proceeds
                        executed.append({
                            "date": d.strftime("%Y-%m-%d"),
                            "ticker": ticker,
                            "action": "sell",
                            "amount_eur": round(proceeds, 2),
                            "price": round(price, 6),
                            "shares": round(shares, 8),
                        })
                elif action == "rebalance":
                    # Rebalance only redistributes the current portfolio — no fresh money.
                    market_value = sum(holdings[t] * float(prices.loc[d, t]) for t in prices.columns)
                    total = market_value + cash
                    if total <= 0:
                        continue
                    for t, target_w in weights.items():
                        if t not in prices.columns:
                            continue
                        target_value = total * target_w
                        price = float(prices.loc[d, t])
                        if price <= 0:
                            continue
                        target_shares = target_value / price
                        delta_shares = target_shares - holdings.get(t, 0.0)
                        delta_eur = delta_shares * price
                        holdings[t] = target_shares
                        # Rebalance moves cash inside the portfolio (no external contribution)
                        cash -= delta_eur
                        if abs(delta_eur) > 0.01:
                            executed.append({
                                "date": d.strftime("%Y-%m-%d"),
                                "ticker": t,
                                "action": "rebalance",
                                "amount_eur": round(delta_eur, 2),
                                "price": round(price, 6),
                                "shares": round(delta_shares, 8),
                            })

        equity_value = cash + sum(
            holdings[t] * float(prices.loc[d, t]) for t in prices.columns if not pd.isna(prices.loc[d, t])
        )
        equity_records.append((d, equity_value))

    equity = pd.Series({d: v for d, v in equity_records}, name="equity")
    return equity, executed


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _contribution_adjusted_returns(equity: pd.Series, executed_trades: list[dict]) -> pd.Series:
    """Serie de retornos diarios neta de aportaciones (time-weighted).

    daily return = (equity_t - equity_{t-1} - inflow_t) / equity_{t-1}, donde
    inflow_t son las aportaciones/retiradas externas del día. Se reutiliza tanto
    para las métricas in-sample como para PSR/DSR.
    """
    if equity.empty or len(equity) < 2:
        return pd.Series(dtype=float)

    inflows = pd.Series(0.0, index=equity.index)
    for t in executed_trades:
        d = pd.Timestamp(t["date"])
        if d not in inflows.index:
            continue
        if t["action"] == "buy":
            inflows.loc[d] += t["amount_eur"]
        elif t["action"] == "sell":
            inflows.loc[d] -= t["amount_eur"]

    eq_prev = equity.shift(1)
    pnl = (equity - eq_prev - inflows) / eq_prev.replace(0, np.nan)
    returns = pnl.dropna()
    return returns[np.isfinite(returns)]


def _compute_metrics(equity: pd.Series, executed_trades: list[dict]) -> dict:
    if equity.empty or len(equity) < 2:
        return {}

    # Strip leading zero/negatives (before first capital injection)
    first_positive = equity[equity > 0].first_valid_index()
    if first_positive is not None:
        equity = equity.loc[first_positive:]

    if equity.empty or len(equity) < 2:
        return {}

    final = float(equity.iloc[-1])

    # Total invested = sum of buy amounts
    total_invested = sum(
        t["amount_eur"] for t in executed_trades if t["action"] == "buy"
    )
    total_proceeds = sum(
        t["amount_eur"] for t in executed_trades if t["action"] == "sell"
    )
    net_invested = max(total_invested - total_proceeds, 1.0)
    total_return_pct = (final - net_invested) / net_invested * 100

    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 0.01)
    cagr = ((final / max(net_invested, 1.0)) ** (1 / years) - 1) * 100 if net_invested > 0 and final > 0 else 0.0

    # Returns on a *contribution-adjusted* (time-weighted) basis.
    returns = _contribution_adjusted_returns(equity, executed_trades)

    if len(returns) > 1:
        vol = float(returns.std() * np.sqrt(252) * 100)
        risk_free = 0.03 / 252
        sharpe = float((returns.mean() - risk_free) / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0
    else:
        vol = 0.0
        sharpe = 0.0

    # Max drawdown on the TWR cumulative — measures *performance* peak-to-trough
    # independent of the cashflow schedule (otherwise DCA-style strategies look better
    # than they are because new contributions push the equity peak up artificially).
    if len(returns) > 1:
        twr_cum = (1.0 + returns).cumprod()
        twr_max = twr_cum.cummax()
        drawdown = (twr_cum - twr_max) / twr_max
        drawdown = drawdown.replace([np.inf, -np.inf], np.nan).dropna()
        if not drawdown.empty:
            max_dd = float(drawdown.min() * 100)
            max_dd_date = drawdown.idxmin().strftime("%Y-%m-%d") if pd.notna(drawdown.min()) else None
        else:
            max_dd = 0.0
            max_dd_date = None
    else:
        max_dd = 0.0
        max_dd_date = None

    n_trades = len(executed_trades)
    buys = [t for t in executed_trades if t["action"] == "buy"]

    return {
        "final_value_eur": round(final, 2),
        "total_invested_eur": round(total_invested, 2),
        "net_invested_eur": round(net_invested, 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr, 2),
        "volatility_pct": round(vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_date": max_dd_date,
        "n_trades": n_trades,
        "n_buys": len(buys),
        "years_covered": round(years, 2),
    }


def _periodic_sharpe(returns: pd.Series) -> float:
    """Sharpe *por periodo* (sin anualizar) de una serie de retornos."""
    r = returns[np.isfinite(returns)]
    if len(r) < 2:
        return 0.0
    std = r.std(ddof=1)
    return float(r.mean() / std) if std > 0 else 0.0


def _trial_sharpes(prices: pd.DataFrame, weights: dict[str, float], base_params: dict) -> list[float]:
    """Sharpe por periodo de cada estrategia del registro sobre el mismo histórico.

    Estos son los "trials" usados por el Deflated Sharpe Ratio: cuantas más
    estrategias se prueban y más dispersos sus Sharpes, mayor el listón a batir.
    """
    sharpes: list[float] = []
    for sdef in STRATEGIES.values():
        try:
            sp = {**sdef.params, **{k: v for k, v in base_params.items() if k in sdef.params}}
            sp["weights"] = weights
            t_df = sdef.runner(prices, **sp)
            eq, ex = _simulate(prices, t_df, weights)
            first_pos = eq[eq > 0].first_valid_index() if not eq.empty else None
            if first_pos is not None:
                eq = eq.loc[first_pos:]
            ret = _contribution_adjusted_returns(eq, ex)
            sharpes.append(_periodic_sharpe(ret))
        except Exception as exc:  # noqa: BLE001
            logger.warning("trial sharpe for {} failed: {}", sdef.key, exc)
    return sharpes


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

async def run_backtest(spec: BacktestSpec) -> BacktestResult:
    if not spec.tickers:
        raise ValueError("At least one ticker is required")

    strategy = get_strategy(spec.strategy_key)
    params = {**strategy.params, **(spec.params or {})}

    start = pd.Timestamp(spec.start_date)
    prices = await _fetch_price_history(spec.tickers, spec.asset_types, start)
    if prices.empty:
        raise ValueError("No price data fetched for the requested tickers")

    # Filter by end_date if provided
    if spec.end_date:
        end = pd.Timestamp(spec.end_date)
        prices = prices[prices.index <= end]
    if prices.empty or len(prices) < 5:
        raise ValueError("Insufficient price data for backtest")

    # Equal weights by default
    weights = params.get("weights") or {t: 1.0 / len(prices.columns) for t in prices.columns}
    params["weights"] = weights

    trades_df = strategy.runner(prices, **params)
    equity, executed = _simulate(prices, trades_df, weights)
    metrics = _compute_metrics(equity, executed)

    # --- Validación robusta al overfitting (López de Prado) -----------------
    # Sharpe *por periodo* de cada estrategia probada sobre el mismo histórico
    # → sirven de "trials" para deflactar el Sharpe (corrección por selección).
    chosen_returns = _contribution_adjusted_returns(equity, executed)
    trial_sharpes = _trial_sharpes(prices, weights, params)
    n_trials = len(STRATEGIES)
    validation = sharpe_metrics(
        chosen_returns.to_numpy(),
        trial_sharpes_periodic=trial_sharpes,
        n_trials=n_trials,
    )
    metrics["psr"] = validation["psr"]
    metrics["deflated_sharpe"] = validation["deflated_sharpe"]
    metrics["n_trials"] = validation["n_trials"]
    metrics["validation"] = validation

    # --- Walk-forward purgado + embargo (out-of-sample) ---------------------
    def _run_fold(fold_prices: pd.DataFrame) -> pd.Series:
        fold_weights = {t: 1.0 / len(fold_prices.columns) for t in fold_prices.columns}
        fold_params = {**params, "weights": fold_weights}
        fold_trades = strategy.runner(fold_prices, **fold_params)
        fold_equity, _ = _simulate(fold_prices, fold_trades, fold_weights)
        return fold_equity

    try:
        metrics["out_of_sample"] = purged_walk_forward(prices, _run_fold)
    except Exception as exc:  # noqa: BLE001
        logger.warning("walk-forward evaluation failed: {}", exc)
        metrics["out_of_sample"] = {"folds": [], "aggregate": {}, "note": "error"}

    equity_curve = [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
        for d, v in equity.items()
        if not pd.isna(v)
    ]

    return BacktestResult(
        strategy_key=spec.strategy_key,
        tickers=list(prices.columns),
        start_date=prices.index[0].strftime("%Y-%m-%d"),
        end_date=prices.index[-1].strftime("%Y-%m-%d"),
        equity_curve=equity_curve,
        trades=executed[:300],  # cap to keep payload small
        metrics=metrics,
    )
