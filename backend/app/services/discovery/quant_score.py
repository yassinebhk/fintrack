"""Quantitative multi-factor scoring — objective ranking, NOT LLM opinion.

Combines validated libraries + standard factor-investing methodology:
- empyrical (Quantopian): Sharpe, Sortino, max drawdown, volatility.
- ta (bukosabino): RSI / trend (via market_scanner signals).
- HQM-style multi-period momentum + cross-sectional z-scoring
  (Multi-Factor Ranking Engine methodology).

Produces TWO objective rankings so the analyst can build a balanced mix:
- momentum_score: rewards strong trend + risk-adjusted return.
- value_score:    rewards beaten-down / oversold quality (contrarian).

The LLM only explains the top-ranked items; it does not choose them.
"""

import numpy as np
import pandas as pd
from loguru import logger

try:
    import empyrical
    _HAS_EMPYRICAL = True
except Exception:  # pragma: no cover
    _HAS_EMPYRICAL = False


def _zscore(values: list[float]) -> list[float]:
    """Winsorized cross-sectional z-score (clip outliers at ±3σ)."""
    arr = np.array([v if v is not None else np.nan for v in values], dtype=float)
    mask = ~np.isnan(arr)
    if mask.sum() < 2:
        return [0.0] * len(values)
    mu = np.nanmean(arr)
    sd = np.nanstd(arr)
    if sd == 0:
        return [0.0] * len(values)
    z = (arr - mu) / sd
    z = np.clip(z, -3, 3)
    return [float(x) if not np.isnan(x) else 0.0 for x in z]


def compute_factors(closes: list[float]) -> dict:
    """Per-asset objective factors from a price series."""
    s = pd.Series([c for c in closes if c is not None], dtype=float)
    if len(s) < 60:
        return {}
    rets = s.pct_change().dropna()
    last = float(s.iloc[-1])

    def mom(days: int) -> float | None:
        if len(s) > days:
            base = float(s.iloc[-days - 1])
            return (last - base) / base if base else None
        return None

    # Multi-period momentum (HQM-style): average of available horizons
    horizons = [mom(21), mom(63), mom(126), mom(252)]
    horizons = [h for h in horizons if h is not None]
    momentum = float(np.mean(horizons)) if horizons else 0.0

    # Risk-adjusted return + risk (empyrical, or numpy fallback)
    if _HAS_EMPYRICAL and len(rets) > 20:
        try:
            sharpe = float(empyrical.sharpe_ratio(rets))
            sortino = float(empyrical.sortino_ratio(rets))
            max_dd = float(empyrical.max_drawdown(rets))
            vol = float(empyrical.annual_volatility(rets))
        except Exception:
            sharpe = sortino = max_dd = vol = 0.0
    else:
        mean, std = rets.mean(), rets.std()
        sharpe = float(mean / std * np.sqrt(252)) if std else 0.0
        sortino = sharpe
        cum = (1 + rets).cumprod()
        max_dd = float(((cum - cum.cummax()) / cum.cummax()).min())
        vol = float(std * np.sqrt(252))

    # 52w range position (0 = low, 1 = high)
    hi, lo = float(s.max()), float(s.min())
    range_pos = (last - lo) / (hi - lo) if hi > lo else 0.5

    return {
        "momentum": round(momentum, 4),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 3),
        "volatility": round(vol, 3),
        "range_pos": round(range_pos, 3),
    }


def score_universe(items: list[dict]) -> list[dict]:
    """Rank items by objective momentum_score and value_score.

    Each item must carry item['factors'] (from compute_factors) and optionally
    item['signals'] (from technical.compute_signals, for RSI).
    Mutates items in place adding 'momentum_score' / 'value_score' and returns sorted-by-momentum.
    """
    valid = [it for it in items if it.get("factors")]
    if len(valid) < 2:
        for it in items:
            it["momentum_score"] = 0.0
            it["value_score"] = 0.0
        return items

    momentum = [it["factors"]["momentum"] for it in valid]
    sharpe = [it["factors"]["sharpe"] for it in valid]
    range_pos = [it["factors"]["range_pos"] for it in valid]
    rsi = [(it.get("signals") or {}).get("rsi", 50) for it in valid]

    z_mom = _zscore(momentum)
    z_sharpe = _zscore(sharpe)
    z_range = _zscore(range_pos)
    z_rsi = _zscore(rsi)

    for i, it in enumerate(valid):
        # MOMENTUM style: strong momentum + good risk-adjusted return + near highs
        it["momentum_score"] = round(0.5 * z_mom[i] + 0.35 * z_sharpe[i] + 0.15 * z_range[i], 3)
        # VALUE/CONTRARIAN style: beaten-down (low range, low RSI) but quality (decent sharpe)
        it["value_score"] = round(-0.45 * z_range[i] - 0.25 * z_rsi[i] + 0.30 * z_sharpe[i], 3)

    for it in items:
        it.setdefault("momentum_score", 0.0)
        it.setdefault("value_score", 0.0)

    items.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
    logger.info("quant scoring done for {} items", len(valid))
    return items
