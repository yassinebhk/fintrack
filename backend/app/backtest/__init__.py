"""Backtest engine — pure pandas/numpy, no vectorbt dependency.

Public entry point:
- `run_backtest(spec)` → equity curve + metrics
- `STRATEGIES` → registry of available strategies and their parameters
"""

from app.backtest.engine import BacktestSpec, BacktestResult, run_backtest
from app.backtest.strategies import STRATEGIES, get_strategy

__all__ = [
    "BacktestSpec",
    "BacktestResult",
    "run_backtest",
    "STRATEGIES",
    "get_strategy",
]
