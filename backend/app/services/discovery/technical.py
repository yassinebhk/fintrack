"""Technical signals computed by the `ta` library (bukosabino/ta, ~4.5k stars).

These are objective, reproducible indicators (RSI, MACD, moving-average trend,
Bollinger position) — NOT LLM opinion. The analyst consumes them as facts.
"""

import pandas as pd
import ta
from loguru import logger


def compute_signals(closes: list[float]) -> dict | None:
    """Compute a compact set of technical signals from a list of close prices."""
    if not closes or len(closes) < 30:
        return None
    s = pd.Series([c for c in closes if c is not None], dtype=float)
    if len(s) < 30:
        return None

    out: dict = {}
    try:
        rsi = ta.momentum.RSIIndicator(s, window=14).rsi().iloc[-1]
        out["rsi"] = round(float(rsi), 1)
        out["rsi_signal"] = "sobreventa" if rsi < 30 else "sobrecompra" if rsi > 70 else "neutral"
    except Exception:
        pass
    try:
        macd_diff = ta.trend.MACD(s).macd_diff().iloc[-1]
        out["macd_signal"] = "alcista" if macd_diff > 0 else "bajista"
    except Exception:
        pass
    try:
        last = float(s.iloc[-1])
        sma50 = ta.trend.SMAIndicator(s, window=min(50, len(s) - 1)).sma_indicator().iloc[-1]
        win200 = min(200, len(s) - 1)
        sma200 = ta.trend.SMAIndicator(s, window=win200).sma_indicator().iloc[-1]
        out["trend"] = "alcista" if sma50 > sma200 else "bajista"
        out["above_sma200"] = bool(last > sma200)
    except Exception:
        pass
    try:
        bb_pct = ta.volatility.BollingerBands(s).bollinger_pband().iloc[-1]
        out["bollinger_pct"] = round(float(bb_pct), 2)  # <0.2 banda baja, >0.8 banda alta
    except Exception:
        pass

    return out or None


def signals_label(sig: dict | None) -> str:
    """One-line human summary of the signals for prompts/UI."""
    if not sig:
        return "sin señales técnicas"
    parts = []
    if "rsi" in sig:
        parts.append(f"RSI {sig['rsi']} ({sig.get('rsi_signal')})")
    if "macd_signal" in sig:
        parts.append(f"MACD {sig['macd_signal']}")
    if "trend" in sig:
        parts.append(f"tendencia {sig['trend']}")
    if "bollinger_pct" in sig:
        bp = sig["bollinger_pct"]
        zone = "banda baja" if bp < 0.2 else "banda alta" if bp > 0.8 else "media"
        parts.append(f"Bollinger {zone}")
    return " · ".join(parts)
