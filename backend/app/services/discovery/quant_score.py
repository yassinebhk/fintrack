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

    # --- Trend regime (absolute momentum, Dual-Momentum style) ---
    sma200 = float(s.rolling(min(200, len(s) - 1)).mean().iloc[-1])
    sma50 = float(s.rolling(min(50, len(s) - 1)).mean().iloc[-1])
    above_sma200 = bool(last > sma200) if sma200 else False
    dist_sma200 = (last - sma200) / sma200 if sma200 else 0.0

    # --- EWMA volatility (RiskMetrics, lambda=0.94) — recency-weighted risk ---
    try:
        ewma_var = (rets ** 2).ewm(alpha=0.06).mean().iloc[-1]
        ewma_vol = float(np.sqrt(ewma_var) * np.sqrt(252)) if ewma_var > 0 else vol
    except Exception:
        ewma_vol = vol

    # --- Mean reversion: how many std the price sits from its 50d mean ---
    try:
        std50 = float(s.rolling(min(50, len(s) - 1)).std().iloc[-1])
        mean_rev_z = (last - sma50) / std50 if std50 else 0.0
    except Exception:
        mean_rev_z = 0.0

    return {
        "momentum": round(momentum, 4),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 3),
        "volatility": round(vol, 3),
        "range_pos": round(range_pos, 3),
        "above_sma200": above_sma200,
        "dist_sma200": round(dist_sma200, 4),
        "ewma_vol": round(ewma_vol, 3),
        "mean_rev_z": round(mean_rev_z, 3),
    }


# Each "judge" votes via a cross-sectional z-score; weights say how much its vote
# counts toward each thesis. Transparent on purpose — you can read why something ranks.
_MOMENTUM_WEIGHTS = {
    "momentum": 0.28,      # multi-period trend (HQM)
    "regimen": 0.22,       # absolute momentum: above its 200d trend
    "riesgo": 0.20,        # risk-adjusted return (Sharpe)
    "tecnico": 0.15,       # RSI/MACD/trend confirmation
    "volatilidad": 0.15,   # prefer lower (EWMA) volatility
}
_VALUE_WEIGHTS = {
    "infravaloracion": 0.30,  # low in its 52w range
    "reversion": 0.22,        # below its own mean (mean-reversion upside)
    "sobreventa": 0.20,       # low RSI
    "calidad": 0.18,          # still decent Sharpe despite the fall
    "volatilidad": 0.10,      # prefer lower volatility
}


def _tech_raw(sig: dict) -> float:
    """Compact technical confirmation score from the `ta` signals."""
    if not sig:
        return 0.0
    score = (sig.get("rsi", 50) - 50) / 25.0  # >0 strong, <0 weak
    if sig.get("macd_signal") == "alcista":
        score += 0.5
    elif sig.get("macd_signal") == "bajista":
        score -= 0.5
    if sig.get("trend") == "alcista":
        score += 0.5
    elif sig.get("trend") == "bajista":
        score -= 0.5
    return score


def score_universe(items: list[dict]) -> list[dict]:
    """Ensemble ranking: several independent 'judges' (momentum, regime, risk-adjusted
    return, technicals, volatility, mean-reversion) each vote via a cross-sectional
    z-score; the votes converge into momentum_score and value_score. Each item also
    gets a 'breakdown' so the contribution of every judge is visible (no black box).

    A market-breadth regime (% of assets above their 200d trend) mildly tilts the
    weighting toward momentum in bull markets and toward value in bear markets.
    """
    valid = [it for it in items if it.get("factors")]
    if len(valid) < 2:
        for it in items:
            it["momentum_score"] = 0.0
            it["value_score"] = 0.0
            it["breakdown"] = {}
        return items

    f = lambda key: [it["factors"].get(key, 0) for it in valid]  # noqa: E731
    z = {
        "momentum": _zscore(f("momentum")),
        "sharpe": _zscore(f("sharpe")),
        "range": _zscore(f("range_pos")),
        "regimen": _zscore(f("dist_sma200")),
        "ewma_vol": _zscore(f("ewma_vol")),
        "mean_rev": _zscore(f("mean_rev_z")),
        "rsi": _zscore([(it.get("signals") or {}).get("rsi", 50) for it in valid]),
        "tecnico": _zscore([_tech_raw(it.get("signals") or {}) for it in valid]),
    }

    # Market regime from breadth: share of the universe above its own 200d trend.
    breadth = sum(1 for it in valid if it["factors"].get("above_sma200")) / len(valid)
    if breadth > 0.55:
        regime, mom_tilt, val_tilt = "alcista", 1.10, 0.95
    elif breadth < 0.45:
        regime, mom_tilt, val_tilt = "bajista", 0.85, 1.10
    else:
        regime, mom_tilt, val_tilt = "neutral", 1.0, 1.0

    for i, it in enumerate(valid):
        mom_parts = {
            "momentum": _MOMENTUM_WEIGHTS["momentum"] * z["momentum"][i],
            "regimen": _MOMENTUM_WEIGHTS["regimen"] * z["regimen"][i],
            "riesgo": _MOMENTUM_WEIGHTS["riesgo"] * z["sharpe"][i],
            "tecnico": _MOMENTUM_WEIGHTS["tecnico"] * z["tecnico"][i],
            "volatilidad": _MOMENTUM_WEIGHTS["volatilidad"] * (-z["ewma_vol"][i]),
        }
        val_parts = {
            "infravaloracion": _VALUE_WEIGHTS["infravaloracion"] * (-z["range"][i]),
            "reversion": _VALUE_WEIGHTS["reversion"] * (-z["mean_rev"][i]),
            "sobreventa": _VALUE_WEIGHTS["sobreventa"] * (-z["rsi"][i]),
            "calidad": _VALUE_WEIGHTS["calidad"] * z["sharpe"][i],
            "volatilidad": _VALUE_WEIGHTS["volatilidad"] * (-z["ewma_vol"][i]),
        }
        it["momentum_score"] = round(sum(mom_parts.values()) * mom_tilt, 3)
        it["value_score"] = round(sum(val_parts.values()) * val_tilt, 3)
        it["breakdown"] = {
            "momentum": {k: round(v, 3) for k, v in mom_parts.items()},
            "value": {k: round(v, 3) for k, v in val_parts.items()},
        }

    for it in items:
        it.setdefault("momentum_score", 0.0)
        it.setdefault("value_score", 0.0)
        it.setdefault("breakdown", {})

    items.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
    logger.info("ensemble scoring done for {} items (regime={}, breadth={:.0%})", len(valid), regime, breadth)
    # stash the regime where the caller (scanner/service) can read it off any item
    for it in valid:
        it["market_regime"] = regime
        it["market_breadth"] = round(breadth, 3)
    return items
