"""Predefined backtest strategies.

Each strategy is a callable that takes a DataFrame of close prices
(rows=date, columns=tickers) and returns a DataFrame of trades:
columns = [date, ticker, action ('buy'|'sell'), amount_eur].

The engine takes care of converting trades into shares and tracking
the equity curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

@dataclass
class StrategyDef:
    key: str
    name: str
    description: str
    params: dict[str, Any]  # default values
    param_specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    runner: Callable[..., pd.DataFrame] = field(default=None)


STRATEGIES: dict[str, StrategyDef] = {}


def register(definition: StrategyDef) -> None:
    STRATEGIES[definition.key] = definition


def get_strategy(key: str) -> StrategyDef:
    if key not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {key}. Available: {list(STRATEGIES)}")
    return STRATEGIES[key]


# ---------------------------------------------------------------------------
# Helper: equal weight across tickers
# ---------------------------------------------------------------------------

def _equal_weights(tickers: list[str]) -> dict[str, float]:
    if not tickers:
        return {}
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}


# ---------------------------------------------------------------------------
# Strategy 1: Buy & Hold (lump sum at the start)
# ---------------------------------------------------------------------------

def strategy_buy_and_hold(prices: pd.DataFrame, **params) -> pd.DataFrame:
    initial = float(params.get("initial_eur", 1000.0))
    weights = params.get("weights") or _equal_weights(list(prices.columns))
    first_day = prices.index[0]
    trades = []
    for ticker, w in weights.items():
        if ticker not in prices.columns:
            continue
        trades.append({
            "date": first_day,
            "ticker": ticker,
            "action": "buy",
            "amount_eur": initial * w,
        })
    return pd.DataFrame(trades)


register(StrategyDef(
    key="buy_and_hold",
    name="Buy & Hold",
    description="Inversión inicial única, repartida equitativamente. Punto de referencia.",
    params={"initial_eur": 1000.0},
    param_specs={
        "initial_eur": {"type": "number", "min": 100, "max": 100000, "default": 1000},
    },
    runner=strategy_buy_and_hold,
))


# ---------------------------------------------------------------------------
# Strategy 2: DCA mensual
# ---------------------------------------------------------------------------

def strategy_dca_monthly(prices: pd.DataFrame, **params) -> pd.DataFrame:
    monthly_eur = float(params.get("monthly_eur", 200.0))
    day_of_month = int(params.get("day_of_month", 1))
    weights = params.get("weights") or _equal_weights(list(prices.columns))

    # Find first trading day >= day_of_month for each month in range
    trades = []
    seen_months: set[tuple[int, int]] = set()
    for d in prices.index:
        ym = (d.year, d.month)
        if ym in seen_months:
            continue
        if d.day >= day_of_month:
            seen_months.add(ym)
            for ticker, w in weights.items():
                if ticker in prices.columns:
                    trades.append({
                        "date": d,
                        "ticker": ticker,
                        "action": "buy",
                        "amount_eur": monthly_eur * w,
                    })
    return pd.DataFrame(trades)


register(StrategyDef(
    key="dca_monthly",
    name="DCA mensual",
    description="Compra fija cada mes, repartida entre activos. La estrategia más simple.",
    params={"monthly_eur": 200.0, "day_of_month": 1},
    param_specs={
        "monthly_eur": {"type": "number", "min": 10, "max": 10000, "default": 200},
        "day_of_month": {"type": "integer", "min": 1, "max": 28, "default": 1},
    },
    runner=strategy_dca_monthly,
))


# ---------------------------------------------------------------------------
# Strategy 3: DCA on-dip (compra cuando hay drawdown vs máximo móvil)
# ---------------------------------------------------------------------------

def strategy_dca_on_dip(prices: pd.DataFrame, **params) -> pd.DataFrame:
    monthly_eur = float(params.get("monthly_eur", 200.0))
    base_pct = float(params.get("base_pct", 0.5))  # % of monthly_eur to invest unconditionally
    trigger_drop_pct = float(params.get("trigger_drop_pct", -5.0))  # threshold to add extra
    extra_multiplier = float(params.get("extra_multiplier", 2.0))  # how much extra on dip
    lookback_days = int(params.get("lookback_days", 60))
    weights = params.get("weights") or _equal_weights(list(prices.columns))

    trades = []
    seen_months: set[tuple[int, int]] = set()
    for d in prices.index:
        ym = (d.year, d.month)
        if ym in seen_months:
            continue
        if d.day < 1:
            continue
        seen_months.add(ym)

        # base DCA
        for ticker, w in weights.items():
            if ticker in prices.columns:
                trades.append({
                    "date": d,
                    "ticker": ticker,
                    "action": "buy",
                    "amount_eur": monthly_eur * base_pct * w,
                })

        # extra on dip
        window = prices.loc[:d].tail(lookback_days)
        for ticker, w in weights.items():
            if ticker not in prices.columns or len(window) < 5:
                continue
            peak = window[ticker].max()
            current = prices.loc[d, ticker]
            if pd.isna(peak) or pd.isna(current) or peak == 0:
                continue
            drop_pct = (current - peak) / peak * 100
            if drop_pct <= trigger_drop_pct:
                extra = monthly_eur * (1 - base_pct) * extra_multiplier * w
                trades.append({
                    "date": d,
                    "ticker": ticker,
                    "action": "buy",
                    "amount_eur": extra,
                })

    return pd.DataFrame(trades)


register(StrategyDef(
    key="dca_on_dip",
    name="DCA on-dip",
    description="DCA mensual base + compra extra cuando un activo cae X% desde su máximo reciente.",
    params={
        "monthly_eur": 200.0,
        "base_pct": 0.5,
        "trigger_drop_pct": -5.0,
        "extra_multiplier": 2.0,
        "lookback_days": 60,
    },
    param_specs={
        "monthly_eur": {"type": "number", "min": 10, "max": 10000, "default": 200},
        "base_pct": {"type": "number", "min": 0, "max": 1, "default": 0.5, "description": "Fracción de la compra que va siempre (sin condición)"},
        "trigger_drop_pct": {"type": "number", "min": -50, "max": 0, "default": -5, "description": "Drop % vs máximo móvil que activa la compra extra"},
        "extra_multiplier": {"type": "number", "min": 1, "max": 5, "default": 2, "description": "Multiplicador del extra en cada dip"},
        "lookback_days": {"type": "integer", "min": 10, "max": 365, "default": 60},
    },
    runner=strategy_dca_on_dip,
))


# ---------------------------------------------------------------------------
# Strategy 4: Rebalance trimestral
# ---------------------------------------------------------------------------

def strategy_rebalance_quarterly(prices: pd.DataFrame, **params) -> pd.DataFrame:
    initial = float(params.get("initial_eur", 1000.0))
    weights = params.get("weights") or _equal_weights(list(prices.columns))
    # Initial buy
    trades = []
    for ticker, w in weights.items():
        if ticker in prices.columns:
            trades.append({
                "date": prices.index[0],
                "ticker": ticker,
                "action": "buy",
                "amount_eur": initial * w,
            })
    # Rebalance every ~63 trading days (~quarterly)
    n = len(prices)
    step = 63
    # We emit a "rebalance" marker — the engine handles it specially.
    for i in range(step, n, step):
        trades.append({
            "date": prices.index[i],
            "ticker": "__REBALANCE__",
            "action": "rebalance",
            "amount_eur": 0.0,
        })
    return pd.DataFrame(trades)


register(StrategyDef(
    key="rebalance_quarterly",
    name="Rebalance trimestral",
    description="Compra inicial repartida y rebalance trimestral a los pesos objetivo.",
    params={"initial_eur": 1000.0},
    param_specs={
        "initial_eur": {"type": "number", "min": 100, "max": 100000, "default": 1000},
    },
    runner=strategy_rebalance_quarterly,
))
