"""Forward paper portfolio (Phase 2) — the system actually 'runs' a sized,
risk-gated portfolio over the buyable universe and tracks it vs a benchmark,
out-of-sample, with NO real money. Real capital is gated behind pre-registered
criteria (see readiness()).

Pipeline each rebalance:
  signals (quant ensemble) → regime pick (momentum in bull / value in bear)
  → inverse-vol sizing → risk gates (caps + crypto sleeve) → drawdown breaker
  → store target weights + entry prices.
Daily mark-to-market builds the NAV curve vs benchmark (MSCI World).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from loguru import logger

from app.services.discovery.quant_score import compute_factors, score_universe
from app.services.systematic.buyable import buyable_meta
from app.services.systematic.risk import apply_gates, drawdown_breached, MAX_WEIGHT_PER_NAME
from app.services.systematic.sizing import inverse_vol_weights

_KEY = "systematic_paper"
_BENCHMARK = "EUNL.DE"   # iShares Core MSCI World UCITS
TOP_K = 6
MIN_DAYS_READY = 56      # 8 weeks
MIN_MARKS_READY = 30


async def _load() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        return row.payload if row and row.payload else {}
    except Exception as exc:
        logger.warning("systematic paper load failed: {}", exc)
        return {}


async def _save(payload: dict) -> None:
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


async def reset() -> dict:
    await _save({})
    return {"reset": True}


async def _scored_universe(scanner) -> list[dict]:
    """Fetch history for the (small) buyable universe and score it with the quant
    ensemble. Skips any ticker whose history is unavailable — never crashes."""
    meta = buyable_meta()
    items = []
    for tk, info in meta.items():
        try:
            hist = await scanner.yahoo.get_history(tk, period="1y")
            closes = [h["close"] for h in (hist or []) if h.get("close")]
            if len(closes) < 60:
                continue
            factors = compute_factors(closes)
            if not factors:
                continue
            items.append({"ticker": tk, "name": info["name"], "asset_class": info["asset_class"],
                          "price": closes[-1], "factors": factors})
        except Exception as exc:
            logger.debug("systematic: {} history failed: {}", tk, exc)
    if items:
        score_universe(items)
    return items


async def rebalance() -> dict:
    """Recompute target weights from current signals and store them."""
    from app.services.discovery.market_scanner import MarketScanner
    scanner = MarketScanner()
    items = await _scored_universe(scanner)
    if len(items) < 4:
        return {"error": "universo insuficiente", "scored": len(items)}

    meta = buyable_meta()
    state = await _load()
    nav_curve = [p["nav"] for p in state.get("marks", [])]

    # Regime: breadth = share of universe above its 200d trend.
    breadth = sum(1 for it in items if it["factors"].get("above_sma200")) / len(items)
    regime = "alcista" if breadth >= 0.5 else "bajista"
    score_key = "momentum_score" if regime == "alcista" else "value_score"

    # Circuit breaker: if the paper NAV has drawn down past the limit → all cash.
    if drawdown_breached(nav_curve):
        weights, picks, note = {}, [], "🛑 circuit-breaker de drawdown activado → 100% liquidez"
    else:
        ranked = sorted(items, key=lambda it: it.get(score_key, 0), reverse=True)
        picks = [it for it in ranked if it.get(score_key, 0) > 0][:TOP_K]
        if len(picks) < 3:  # weak breadth → add defensives (gold/bonds) if present
            defensive = [it for it in items if it["asset_class"] in ("commodity", "bond")]
            for d in defensive:
                if d not in picks:
                    picks.append(d)
            picks = picks[:TOP_K]
        vols = {it["ticker"]: it["factors"].get("volatility") for it in picks}
        weights = inverse_vol_weights(vols, max_weight=MAX_WEIGHT_PER_NAME)
        weights = apply_gates(weights, meta)
        note = f"régimen {regime} (breadth {breadth:.0%}) · sizing inverse-vol + gates"

    entry_prices = {it["ticker"]: it["price"] for it in picks}
    now = datetime.now(timezone.utc)
    state.setdefault("inception", now.isoformat())
    state["benchmark"] = _BENCHMARK
    state["holdings"] = weights
    state["entry_prices"] = entry_prices
    state["last_rebalance"] = now.isoformat()
    state["regime"] = regime
    state["note"] = note
    state.setdefault("marks", [])
    # benchmark entry price for the leg starting now
    try:
        bp = await scanner.yahoo.get_price(_BENCHMARK)
        state["benchmark_entry"] = (bp or {}).get("price")
    except Exception:
        state["benchmark_entry"] = state.get("benchmark_entry")
    # NAV continuity: the leg starts at the current NAV (or 100 at inception)
    state["leg_start_nav"] = nav_curve[-1] if nav_curve else 100.0
    state["leg_start_bench_nav"] = state.get("_bench_nav", 100.0)
    await _save(state)
    return {"regime": regime, "breadth": round(breadth, 2), "picks": len(weights),
            "holdings": weights, "note": note}


async def mark() -> dict:
    """Mark-to-market: append today's NAV (portfolio + benchmark) to the curve."""
    from app.services.discovery.market_scanner import MarketScanner
    scanner = MarketScanner()
    state = await _load()
    if not state.get("last_rebalance"):
        return {"error": "sin rebalanceo todavía"}
    holdings = state.get("holdings", {})
    entry = state.get("entry_prices", {})

    # portfolio return since the last rebalance
    port_ret = 0.0
    for tk, w in holdings.items():
        e = entry.get(tk)
        if not e:
            continue
        try:
            p = (await scanner.yahoo.get_price(tk) or {}).get("price")
        except Exception:
            p = None
        if p and e:
            port_ret += w * (p / e - 1.0)
    leg_nav = state.get("leg_start_nav", 100.0) * (1 + port_ret)

    # benchmark return since the last rebalance
    bench_ret = 0.0
    be = state.get("benchmark_entry")
    if be:
        try:
            bp = (await scanner.yahoo.get_price(state.get("benchmark", _BENCHMARK)) or {}).get("price")
        except Exception:
            bp = None
        if bp:
            bench_ret = bp / be - 1.0
    bench_nav = state.get("leg_start_bench_nav", 100.0) * (1 + bench_ret)

    today = datetime.now(timezone.utc).date().isoformat()
    marks = [m for m in state.get("marks", []) if m.get("date") != today]  # one per day
    marks.append({"date": today, "nav": round(leg_nav, 4), "bench": round(bench_nav, 4)})
    state["marks"] = marks[-400:]
    state["_bench_nav"] = bench_nav
    await _save(state)
    return {"date": today, "nav": round(leg_nav, 2), "bench": round(bench_nav, 2),
            "invested_pct": round(sum(holdings.values()) * 100, 1)}


def _ann_sharpe(navs: list[float]) -> float | None:
    if len(navs) < 10:
        return None
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1]]
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    sd = (sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5
    return (m / sd * math.sqrt(252)) if sd > 0 else None


def _max_dd(navs: list[float]) -> float:
    peak, mdd = navs[0] if navs else 1, 0.0
    for v in navs:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return mdd


async def report() -> dict:
    state = await _load()
    marks = state.get("marks", [])
    if not marks:
        return {"status": "sin marcas todavía", "holdings": state.get("holdings", {}),
                "readiness": {"ready": False, "note": "Aún no ha empezado a marcar NAV."}}
    navs = [m["nav"] for m in marks]
    benches = [m["bench"] for m in marks]
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(state["inception"])).days
    port_ret = navs[-1] / navs[0] - 1
    bench_ret = benches[-1] / benches[0] - 1
    p_sharpe = _ann_sharpe(navs)
    b_sharpe = _ann_sharpe(benches)
    # López de Prado: is the Sharpe statistically real, not luck? (PSR / Deflated Sharpe)
    psr = dsr = None
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1]]
    if len(rets) >= 5:
        try:
            from app.backtest.validation import sharpe_metrics
            sm = sharpe_metrics(rets)
            psr, dsr = sm.get("psr"), sm.get("deflated_sharpe")
        except Exception as exc:
            logger.debug("systematic PSR failed: {}", exc)
    out = {
        "inception": state.get("inception"), "days": days, "marks": len(marks),
        "regime": state.get("regime"), "note": state.get("note"),
        "return_pct": round(port_ret * 100, 2), "benchmark_return_pct": round(bench_ret * 100, 2),
        "alpha_pct": round((port_ret - bench_ret) * 100, 2),
        "sharpe": round(p_sharpe, 2) if p_sharpe is not None else None,
        "benchmark_sharpe": round(b_sharpe, 2) if b_sharpe is not None else None,
        "psr": psr, "deflated_sharpe": dsr,
        "max_drawdown_pct": round(_max_dd(navs) * 100, 1),
        "invested_pct": round(sum(state.get("holdings", {}).values()) * 100, 1),
        "holdings": state.get("holdings", {}),
    }
    out["readiness"] = _readiness(out)
    return out


def _readiness(r: dict) -> dict:
    checks = {
        "sample_ok": r["days"] >= MIN_DAYS_READY and r["marks"] >= MIN_MARKS_READY,
        "beats_benchmark_return": r["alpha_pct"] > 0,
        "beats_benchmark_sharpe": (r["sharpe"] is not None and r["benchmark_sharpe"] is not None
                                   and r["sharpe"] > r["benchmark_sharpe"]),
        "edge_significant": (r.get("psr") is not None and r["psr"] >= 0.75),
        "no_blowup": r["max_drawdown_pct"] > -25,
    }
    return {**checks, "ready": all(checks.values()),
            "verdict": ("APTO para piloto real mínimo" if all(checks.values())
                        else f"NO apto — sigue en papel ({r['days']}/{MIN_DAYS_READY} días)")}
