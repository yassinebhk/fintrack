"""Technical signals computed by the `ta` library (bukosabino/ta, ~4.5k stars).

These are objective, reproducible indicators (RSI, MACD, moving-average trend,
Bollinger position) — NOT LLM opinion. The analyst consumes them as facts.
"""

import pandas as pd
import ta
from loguru import logger


def compute_signals(closes: list[float], highs: list[float] | None = None,
                    lows: list[float] | None = None, volumes: list[float] | None = None) -> dict | None:
    """Compute a compact set of technical signals from close prices. If OHLCV is
    provided (highs/lows/volumes aligned with closes), also computes ATR (+ a 2×ATR
    stop suggestion), ADX (trend strength) and relative volume."""
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

    # ATR / ADX need OHLC; relative volume needs volume — only if provided & aligned.
    if highs is not None and lows is not None and len(highs) == len(closes) and len(lows) == len(closes):
        h = pd.Series([x for x in highs], dtype=float)
        low = pd.Series([x for x in lows], dtype=float)
        last = float(s.iloc[-1])
        try:
            atr = ta.volatility.AverageTrueRange(high=h, low=low, close=s, window=14).average_true_range().iloc[-1]
            if last > 0 and atr == atr:  # atr==atr filters NaN
                out["atr_pct"] = round(float(atr) / last * 100, 2)
                out["stop_pct"] = round(-2.0 * float(atr) / last * 100, 1)  # a 2×ATR protective stop
        except Exception:
            pass
        try:
            adx = ta.trend.ADXIndicator(high=h, low=low, close=s, window=14).adx().iloc[-1]
            if adx == adx:
                out["adx"] = round(float(adx))
                out["adx_signal"] = "tendencia fuerte" if adx >= 25 else "sin tendencia clara"
        except Exception:
            pass
    if volumes is not None and len(volumes) == len(closes):
        try:
            v = pd.Series([x for x in volumes], dtype=float)
            avg = float(v.iloc[-20:].mean())
            if avg and avg > 0:
                rvol = float(v.iloc[-1]) / avg
                out["rvol"] = round(rvol, 2)
                out["volume_signal"] = "alto" if rvol > 1.5 else "bajo" if rvol < 0.6 else "normal"
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
    if "adx" in sig:
        parts.append(f"ADX {sig['adx']} ({sig.get('adx_signal')})")
    if "atr_pct" in sig:
        parts.append(f"ATR {sig['atr_pct']}%")
    if "volume_signal" in sig:
        parts.append(f"volumen {sig['volume_signal']}")
    return " · ".join(parts)
