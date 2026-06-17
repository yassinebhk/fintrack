"""Objective probability model for crypto price-threshold markets.

For a market like "Will BTC be above $T by <date>" we estimate P(S_T ≥ T) with a
driftless lognormal (GBM, μ=0 — we do NOT assume a direction; that would be a bias)
using Binance spot + realized volatility. This is the only family we model, because
it has an objective anchor; politics/sports are out of scope (no model = no edge,
only opinion). The market's YES price is the implied probability; the gap is our
(testable) edge.
"""

from __future__ import annotations

import math
import re

_ABOVE = re.compile(r"\b(above|over|exceed|greater|more than|at least|≥|>=|por encima|m[aá]s de)\b", re.I)
_BELOW = re.compile(r"\b(below|under|less than|≤|<=|por debajo|menos de)\b", re.I)
# Barrier/touch markets ("reach/hit/dip to $T") resolve on ANY touch over the period,
# not on the terminal price — our terminal lognormal can't price them, so we exclude them.
_BARRIER = re.compile(r"\b(reach|hit|touch|dip to|fall to|drop to|surpass|new (all[- ]?time )?high|all[- ]?time high|\bath\b)\b", re.I)


def is_terminal_threshold(question: str) -> bool:
    """True only for clean terminal 'be above/below $T on|by <date>' markets."""
    q = question or ""
    return bool((_ABOVE.search(q) or _BELOW.search(q)) and not _BARRIER.search(q))


def detect_direction(question: str) -> str:
    """'above' or 'below' for terminal threshold markets."""
    q = question or ""
    if _BELOW.search(q) and not _ABOVE.search(q):
        return "below"
    return "above"


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_above(spot: float, target: float, vol_annual: float, years: float) -> float | None:
    """Driftless GBM P(S_T ≥ target). Returns None if inputs are unusable."""
    if not spot or not target or spot <= 0 or target <= 0:
        return None
    if not vol_annual or vol_annual <= 0 or years is None or years <= 0:
        return None
    denom = vol_annual * math.sqrt(years)
    if denom <= 0:
        return None
    z = (math.log(spot / target) - 0.5 * vol_annual ** 2 * years) / denom
    return _phi(z)


def model_probability(spot: float, target: float, vol_annual: float, years: float,
                      direction: str) -> float | None:
    p_above = prob_above(spot, target, vol_annual, years)
    if p_above is None:
        return None
    return p_above if direction == "above" else (1.0 - p_above)
