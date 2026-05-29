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
# Materiality: how much real money is at stake. A signal on a near-zero position
# is noise — acting on it changes nothing. We weight urgency by € at stake.
_IMMATERIAL_EUR = 30.0     # below this € value → acting is pointless
_IMMATERIAL_WEIGHT = 1.0   # and below this % of the portfolio


def _materiality(value_eur: float, weight: float) -> tuple[str, bool]:
    """Return (label, is_immaterial). Immaterial = too little money to matter."""
    if value_eur < _IMMATERIAL_EUR and weight < _IMMATERIAL_WEIGHT:
        return ("insignificante", True)
    if weight >= 15 or value_eur >= 1000:
        return ("alta", False)
    if weight >= 5 or value_eur >= 300:
        return ("media", False)
    return ("baja", False)


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
    value_eur = pos.get("market_value_base", 0) or 0
    invested_eur = pos.get("cost_basis", 0) or 0
    pnl_eur = pos.get("gain_loss", 0) or 0
    if pnl_pct <= -10 and thesis_broken:
        bias = (f"⚠️ Sesgo: invertiste {invested_eur:.0f}€ y hoy valen {value_eur:.0f}€ "
                f"({pnl_eur:+.0f}€, {pnl_pct:.0f}%), con la tendencia ROTA. Aguantar 'hasta recuperar "
                "lo invertido' es efecto disposición — tu precio de entrada no influye en lo que el "
                "activo hará ahora. Decide por la tesis, no por volver a 0.")
    elif pnl_pct >= 30 and thesis_intact:
        bias = (f"⚠️ Sesgo: {invested_eur:.0f}€ invertidos valen hoy {value_eur:.0f}€ "
                f"({pnl_eur:+.0f}€, +{pnl_pct:.0f}%) y la tendencia sigue FUERTE. Vender solo por "
                "'asegurar la ganancia' también es efecto disposición — cortar a los ganadores que "
                "siguen subiendo. Si reduces, que sea por concentración/riesgo, no por el verde.")

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


_REVIEW_KEY = "position_review"
_REVIEW_TTL_HOURS = 6


async def review_portfolio(force: bool = False) -> dict:
    """Cached entry point: serve the last review (≤6h) unless force=True. The review
    fetches history for every holding (~slow on free tier), so caching keeps it
    instant. Cache lives in json_cache (survives redeploys)."""
    from datetime import datetime, timedelta, timezone

    if not force:
        try:
            from sqlalchemy import select

            from app.db import session_scope
            from app.models import JsonCache
            async with session_scope() as s:
                row = (await s.execute(select(JsonCache).where(JsonCache.key == _REVIEW_KEY))).scalar_one_or_none()
            if row and row.payload:
                upd = row.updated_at
                if upd and upd.tzinfo is None:
                    upd = upd.replace(tzinfo=timezone.utc)
                if upd and datetime.now(timezone.utc) - upd < timedelta(hours=_REVIEW_TTL_HOURS):
                    return {**row.payload, "cached_at": upd.isoformat()}
        except Exception as exc:
            logger.debug("position_review cache read failed: {}", exc)

    result = await _compute_review()
    try:
        from app.db import session_scope, upsert_insert
        from app.models import JsonCache
        stmt = upsert_insert()(JsonCache).values(
            key=_REVIEW_KEY, payload=result, updated_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(
            index_elements=["key"],
            set_={"payload": result, "updated_at": datetime.now(timezone.utc)},
        )
        async with session_scope() as s:
            await s.execute(stmt)
    except Exception as exc:
        logger.debug("position_review cache write failed: {}", exc)
    return result


async def _compute_review() -> dict:
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
        value_eur = round(pos.get("market_value_base", 0) or 0, 2)
        invested_eur = round(pos.get("cost_basis", 0) or 0, 2)
        weight = round(pos.get("weight", 0) or 0, 1)
        pnl_eur = round(pos.get("gain_loss", 0) or 0, 2)
        mat_label, immaterial = _materiality(value_eur, weight)

        reasons = list(ev["reasons"])
        bias_flag = ev["bias_flag"]
        # Materiality context: a signal on a near-zero position is irrelevant.
        if immaterial:
            reasons.append(
                f"💤 Importe insignificante (~{value_eur:.0f}€, {weight:.1f}% de tu cartera): "
                "la señal es correcta pero actuar aquí no cambia nada — prioriza lo que pesa."
            )
            bias_flag = None  # don't nag about bias on a 2€ position

        reviews.append({
            "ticker": ticker,
            "name": pos.get("name") or ticker,
            "type": pos.get("type"),
            "broker": pos.get("broker"),
            "signal": ev["signal"],
            "materiality": mat_label,
            "immaterial": immaterial,
            "reasons": reasons,
            "bias_flag": bias_flag,
            "metrics": ev["metrics"],
            # P&L + amounts shown as CONTEXT (and used for materiality, not as the driver):
            "pnl_pct": round(pos.get("gain_loss_pct", 0) or 0, 2),
            "pnl_eur": pnl_eur,
            "invested_eur": invested_eur,
            "value_eur": value_eur,
            "weight_pct": weight,
        })

    # Order by urgency AND money at stake: material ROTAR/REDUCIR first, immaterial last.
    rank = {"ROTAR": 0, "REDUCIR": 1, "VIGILAR": 2, "MANTENER": 3, "SIN_DATOS": 4}
    reviews.sort(key=lambda r: (r.get("immaterial", False), rank.get(r["signal"], 9), -r.get("value_eur", 0)))

    # € that actually need attention = material ROTAR/REDUCIR positions.
    attention_eur = round(sum(
        r["value_eur"] for r in reviews
        if r["signal"] in ("ROTAR", "REDUCIR") and not r.get("immaterial")
    ), 2)

    return {
        "reviews": reviews,
        "summary": {
            "rotar": sum(1 for r in reviews if r["signal"] == "ROTAR"),
            "reducir": sum(1 for r in reviews if r["signal"] == "REDUCIR"),
            "vigilar": sum(1 for r in reviews if r["signal"] == "VIGILAR"),
            "mantener": sum(1 for r in reviews if r["signal"] == "MANTENER"),
            "rotar_material": sum(1 for r in reviews if r["signal"] == "ROTAR" and not r.get("immaterial")),
            "attention_eur": attention_eur,
        },
        "disclaimer": (
            "Análisis objetivo basado en señales prospectivas (tendencia, momentum, riesgo desde "
            "máximos, concentración). NO se basa en tu precio de entrada (eso sería efecto disposición). "
            "Es análisis educativo, no recomendación de compra/venta."
        ),
    }
