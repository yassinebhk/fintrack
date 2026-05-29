"""Objective position review — should you keep / trim / rotate each holding?

DESIGN PRINCIPLE (anti-bias): the keep/sell signal is FORWARD-LOOKING. It is based
on the asset's current health (trend, momentum, risk from its own peak) and your
portfolio concentration — NOT on your entry price. Anchoring on your P&L vs cost is
the *disposition effect* (selling winners early, holding losers to "break even"),
the #1 retail bias. Your P&L is shown only as context (tax / rebalancing) and the
engine explicitly flags when your instinct would be that bias.

All signals are deterministic math over real prices. No LLM decides anything; an
optional LLM only phrases the explanation (with a template fallback).
"""

from __future__ import annotations

import numpy as np
from loguru import logger

from app.services.discovery.market_scanner import MarketScanner
from app.services.discovery.quant_score import compute_factors
from app.services.discovery.technical import compute_signals

# Thresholds (transparent, tunable).
_DD_WATCH = -15.0      # drawdown from peak (%) → caution
_DD_HIGH = -25.0       # drawdown from peak (%) → elevated risk
_OVERWEIGHT = 30.0     # single-position weight (%) → concentration risk
_OVERWEIGHT_SOFT = 22.0


def _history_ticker(ticker: str, asset_type: str) -> str:
    """Map a holding to a Yahoo symbol for history (crypto needs a quote suffix)."""
    t = (ticker or "").upper()
    if asset_type == "crypto" and not t.endswith(("-USD", "-EUR")):
        return f"{t}-USD"
    return t


async def _asset_metrics(scanner: MarketScanner, ticker: str, asset_type: str) -> dict | None:
    sym = _history_ticker(ticker, asset_type)
    try:
        hist = await scanner.yahoo.get_history(sym, period="1y")
    except Exception as exc:
        logger.debug("position_review: history {} failed: {}", sym, exc)
        return None
    closes = [h["close"] for h in (hist or []) if h.get("close")]
    if len(closes) < 60:
        return None
    factors = compute_factors(closes)        # momentum, sharpe, max_drawdown, vol, above_sma200, dist_sma200, ...
    signals = compute_signals(closes) or {}  # rsi, macd, trend, ...
    # Drawdown from the asset's OWN recent peak (not from the user's entry).
    last = closes[-1]
    peak = max(closes)
    dd_from_peak = (last - peak) / peak * 100 if peak else 0.0
    return {"factors": factors, "signals": signals, "dd_from_peak": round(dd_from_peak, 1),
            "last_close": last}


def _evaluate(pos: dict, m: dict) -> dict:
    """Pure decision logic. Returns signal + reasons + bias flag."""
    f = m.get("factors") or {}
    s = m.get("signals") or {}
    above_sma200 = bool(f.get("above_sma200"))
    momentum = f.get("momentum", 0) or 0          # multi-period, fraction
    rsi = s.get("rsi")
    trend = s.get("trend")
    dd_peak = m.get("dd_from_peak", 0)
    weight = pos.get("weight", 0) or 0
    pnl_pct = pos.get("gain_loss_pct", 0) or 0

    # --- Forward-looking thesis health (NOT based on entry price) ---
    thesis_intact = above_sma200 and momentum >= 0
    thesis_broken = (not above_sma200) and momentum < 0
    risk_high = dd_peak <= _DD_HIGH
    risk_watch = dd_peak <= _DD_WATCH
    overbought = rsi is not None and rsi >= 75

    reasons = []
    # Build the objective signal.
    if pos.get("type") not in ("crypto",) and weight >= _OVERWEIGHT:
        signal = "REDUCIR"
        reasons.append(f"Concentración alta: pesa {weight:.0f}% de tu cartera (riesgo de concentración, no por tu ganancia).")
    elif thesis_broken and risk_high:
        signal = "ROTAR"
        reasons.append(f"Tendencia rota (bajo su media de 200 sesiones) y momentum negativo, con caída {dd_peak:.0f}% desde su máximo. La tesis ya no la sostiene.")
    elif thesis_broken or risk_watch:
        signal = "VIGILAR"
        if thesis_broken:
            reasons.append("Tendencia debilitada: por debajo de su media de 200 sesiones y momentum negativo.")
        if risk_watch:
            reasons.append(f"Caída {dd_peak:.0f}% desde su máximo reciente; vigila el riesgo.")
    elif thesis_intact:
        signal = "MANTENER"
        reasons.append(f"Tesis intacta: sobre su media de 200 sesiones, tendencia {trend or 'alcista'}, momentum positivo.")
        if overbought:
            reasons.append(f"Aviso: RSI {rsi:.0f} (sobrecompra) — posible pausa, no necesariamente venta.")
        if weight >= _OVERWEIGHT_SOFT:
            reasons.append(f"Pesa {weight:.0f}%: si te incomoda la concentración, valora rebalancear (por riesgo, no por P&L).")
    else:
        signal = "VIGILAR"
        reasons.append("Señales mixtas; sin tendencia clara.")

    # --- Disposition-effect detection (the bias the user asked to avoid) ---
    bias = None
    if pnl_pct <= -10 and thesis_broken:
        bias = (f"⚠️ Sesgo: llevas {pnl_pct:.0f}% de pérdida y la tendencia está ROTA. "
                "Aguantar 'hasta recuperar lo invertido' es efecto disposición — tu precio de entrada "
                "no influye en lo que el activo hará ahora. Decide por la tesis, no por volver a 0.")
    elif pnl_pct >= 30 and thesis_intact:
        bias = (f"⚠️ Sesgo: llevas +{pnl_pct:.0f}% y la tendencia sigue FUERTE. "
                "Vender solo por 'asegurar la ganancia' también es efecto disposición — cortar a los "
                "ganadores que siguen subiendo. Si reduces, que sea por concentración/riesgo, no por el verde.")

    return {"signal": signal, "reasons": reasons, "bias_flag": bias,
            "metrics": {
                "above_sma200": above_sma200,
                "momentum_pct": round(momentum * 100, 1),
                "rsi": rsi,
                "trend": trend,
                "drawdown_from_peak_pct": dd_peak,
                "sharpe": f.get("sharpe"),
                "weight_pct": round(weight, 1),
            }}


async def review_portfolio() -> dict:
    """Per-holding objective keep/trim/rotate signals with explanations + bias flags."""
    from app.services.portfolio import PortfolioService

    portfolio = await PortfolioService().calculate_portfolio()
    positions = portfolio.get("positions") or []
    scanner = MarketScanner()

    reviews = []
    for pos in positions:
        ticker = pos.get("ticker")
        if not ticker:
            continue
        m = await _asset_metrics(scanner, ticker, pos.get("type", "stock"))
        if not m:
            reviews.append({
                "ticker": ticker, "name": pos.get("name") or ticker,
                "signal": "SIN_DATOS", "reasons": ["Sin histórico suficiente para evaluar objetivamente."],
                "bias_flag": None,
                "pnl_pct": pos.get("gain_loss_pct"), "weight_pct": round(pos.get("weight", 0) or 0, 1),
            })
            continue
        ev = _evaluate(pos, m)
        reviews.append({
            "ticker": ticker,
            "name": pos.get("name") or ticker,
            "type": pos.get("type"),
            "broker": pos.get("broker"),
            "signal": ev["signal"],
            "reasons": ev["reasons"],
            "bias_flag": ev["bias_flag"],
            "metrics": ev["metrics"],
            # P&L shown as CONTEXT only (not the decision driver):
            "pnl_pct": round(pos.get("gain_loss_pct", 0) or 0, 2),
            "pnl_eur": round(pos.get("gain_loss", 0) or 0, 2),
            "invested_eur": round(pos.get("cost_basis", 0) or 0, 2),
            "value_eur": round(pos.get("market_value_base", 0) or 0, 2),
            "weight_pct": round(pos.get("weight", 0) or 0, 1),
        })

    # Order by urgency: ROTAR > REDUCIR > VIGILAR > MANTENER > SIN_DATOS
    rank = {"ROTAR": 0, "REDUCIR": 1, "VIGILAR": 2, "MANTENER": 3, "SIN_DATOS": 4}
    reviews.sort(key=lambda r: rank.get(r["signal"], 9))

    return {
        "reviews": reviews,
        "summary": {
            "rotar": sum(1 for r in reviews if r["signal"] == "ROTAR"),
            "reducir": sum(1 for r in reviews if r["signal"] == "REDUCIR"),
            "vigilar": sum(1 for r in reviews if r["signal"] == "VIGILAR"),
            "mantener": sum(1 for r in reviews if r["signal"] == "MANTENER"),
        },
        "disclaimer": (
            "Análisis objetivo basado en señales prospectivas (tendencia, momentum, riesgo desde "
            "máximos, concentración). NO se basa en tu precio de entrada (eso sería efecto disposición). "
            "Es análisis educativo, no recomendación de compra/venta."
        ),
    }
