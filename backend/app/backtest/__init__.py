"""Backtest engine — pure pandas/numpy, no vectorbt dependency.

Public entry point:
- `run_backtest(spec)` → equity curve + metrics
- `STRATEGIES` → registry of available strategies and their parameters
"""

from app.backtest.engine import BacktestSpec, BacktestResult, run_backtest
from app.backtest.strategies import STRATEGIES, get_strategy
from app.backtest.validation import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    purged_walk_forward,
    sharpe_metrics,
)

__all__ = [
    "BacktestSpec",
    "BacktestResult",
    "run_backtest",
    "STRATEGIES",
    "get_strategy",
    "probabilistic_sharpe_ratio",
    "deflated_sharpe_ratio",
    "sharpe_metrics",
    "purged_walk_forward",
]
