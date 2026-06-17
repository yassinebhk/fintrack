"""Polymarket Paper-Trading Lab — rigorous, no real money, no wallet.

Pipeline (read-only):
  1) scan crypto price-threshold markets → implied probability (market YES price)
  2) compute an OBJECTIVE model probability (driftless lognormal from Binance
     spot + realized vol)  →  edge = model − implied
  3) when |edge| ≥ MIN_EDGE, log a PAPER bet sized with fractional Kelly
  4) as markets resolve, score realized P&L, hit rate, and — the real test —
     whether our model is better CALIBRATED than the market (Brier score).

PRE-REGISTERED success criteria (set up front to avoid moving goalposts / false
positives). Only if ALL hold do we even discuss a tiny real-money pilot:
  • ≥ MIN_RESOLVED resolved paper bets (enough sample)
  • model Brier < market Brier (we actually beat the market's own prices)
  • mean net ROI/bet > 0 with a 95% CI whose lower bound > 0, AFTER a fee/slippage
    haircut of FEE_HAIRCUT per trade
  • positive cumulative paper P&L
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from loguru import logger

from app.services.polymarket.binance import BinanceSpotClient
from app.services.polymarket.client import PolymarketClient
from app.services.polymarket.model import detect_direction, model_probability
from app.services.polymarket.scanner import PolymarketScanner

_KEY = "polymarket_paper_ledger"

# --- tunables (paper) ---
PAPER_BANKROLL = 1000.0      # notional paper units
MIN_EDGE = 0.06              # 6 percentage points model-vs-implied to act
KELLY_FRACTION = 0.25        # quarter-Kelly (conservative)
MAX_STAKE_FRAC = 0.10        # never risk >10% of bankroll on one bet
MIN_VOLUME_24H = 2000.0      # only liquid-enough markets
FEE_HAIRCUT = 0.02           # 2% per trade, applied in the report (conservative)

# --- pre-registered success bar ---
MIN_RESOLVED = 50


async def _load() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        return row.payload if row and row.payload else {"bets": []}
    except Exception as exc:
        logger.warning("polymarket lab load failed: {}", exc)
        return {"bets": []}


async def _save(payload: dict) -> None:
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


def _years_until(end_date: str) -> float | None:
    if not end_date:
        return None
    try:
        s = end_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (dt - datetime.now(timezone.utc)).total_seconds()
        return secs / (365.25 * 86400) if secs > 0 else None
    except Exception:
        return None


async def find_edges(limit: int = 40) -> list[dict]:
    """Return signals where the model disagrees with the market by ≥ MIN_EDGE."""
    scanner = PolymarketScanner()
    binance = BinanceSpotClient()
    res = await scanner.scan(limit=limit)
    vol_cache: dict[str, float] = {}
    out: list[dict] = []
    for m in res.get("markets", []):
        symbol = m.get("binance_symbol")
        spot = m.get("binance_spot")
        target = m.get("target_price")
        implied = m.get("yes_price")            # market P(question true)
        end_date = m.get("end_date")
        question = m.get("question") or ""
        if not (symbol and spot and target and implied is not None and end_date):
            continue
        if (m.get("volume_24h") or 0) < MIN_VOLUME_24H:
            continue
        years = _years_until(end_date)
        if not years:
            continue
        if symbol not in vol_cache:
            from app.services.polymarket.deribit import dvol_annualized
            v, src = await dvol_annualized(symbol), "DVOL-implícita"   # forward-looking (BTC/ETH)
            if not v:
                v, src = await binance.realized_vol_yang_zhang(symbol), "Yang-Zhang"  # efficient OHLC
            if not v:
                v, src = await binance.realized_vol_annualized(symbol), "close-to-close"
            if not v:
                continue
            vol_cache[symbol] = (v, src)
        vol, vol_src = vol_cache[symbol]
        direction = detect_direction(question)
        model_p = model_probability(spot, target, vol, years, direction)
        if model_p is None:
            continue
        edge = model_p - implied
        if abs(edge) < MIN_EDGE:
            continue
        side = "YES" if edge > 0 else "NO"
        entry = implied if side == "YES" else (1.0 - implied)
        win_p = model_p if side == "YES" else (1.0 - model_p)
        # fractional Kelly on a binary bet bought at `entry`
        if entry <= 0 or entry >= 1:
            continue
        kelly = (win_p - entry) / (1.0 - entry)
        kelly = max(0.0, min(kelly, 1.0))
        stake = round(min(PAPER_BANKROLL * KELLY_FRACTION * kelly, PAPER_BANKROLL * MAX_STAKE_FRAC), 2)
        if stake <= 0:
            continue
        out.append({
            "market_id": str(m.get("id")), "question": question, "url": m.get("url"),
            "symbol": symbol, "spot_at_signal": spot, "target": target, "direction": direction,
            "end_date": end_date, "side": side, "entry_price": round(entry, 4),
            "model_prob_yes": round(model_p, 4), "implied_prob_yes": round(implied, 4),
            "edge": round(edge, 4), "win_prob": round(win_p, 4),
            "vol_annual": round(vol, 4), "vol_source": vol_src, "years": round(years, 4), "stake": stake,
        })
    return out


async def log_paper_bets(limit: int = 40) -> dict:
    """Append new paper bets for markets not already open in the ledger."""
    signals = await find_edges(limit=limit)
    data = await _load()
    open_ids = {b["market_id"] for b in data.get("bets", []) if b.get("status") == "open"}
    added = 0
    now = datetime.now(timezone.utc).isoformat()
    for s in signals:
        if s["market_id"] in open_ids:
            continue
        data.setdefault("bets", []).append({**s, "opened_at": now, "status": "open",
                                            "outcome_yes": None, "pnl": None})
        open_ids.add(s["market_id"])
        added += 1
    if added:
        await _save(data)
    return {"signals": len(signals), "new_bets": added, "open_total": len(open_ids)}


async def evaluate() -> dict:
    """Resolve matured open bets and compute realized P&L."""
    data = await _load()
    client = PolymarketClient()
    resolved_now = 0
    for b in data.get("bets", []):
        if b.get("status") != "open":
            continue
        mk = await client.get_market_by_id(b["market_id"])
        if not mk or not mk.get("closed"):
            continue
        yes_final = None
        for o in mk.get("outcomes", []):
            if str(o.get("outcome", "")).lower() in ("yes", "sí", "si", "up"):
                yes_final = o.get("price")
                break
        if yes_final is None and mk.get("outcomes"):
            yes_final = mk["outcomes"][0].get("price")
        if yes_final is None:
            continue
        outcome_yes = 1 if yes_final >= 0.5 else 0
        won = (b["side"] == "YES" and outcome_yes == 1) or (b["side"] == "NO" and outcome_yes == 0)
        shares = b["stake"] / b["entry_price"] if b["entry_price"] else 0
        pnl = round((shares - b["stake"]) if won else (-b["stake"]), 2)
        b.update({"status": "resolved", "outcome_yes": outcome_yes, "won": won,
                  "pnl": pnl, "resolved_at": datetime.now(timezone.utc).isoformat()})
        resolved_now += 1
    if resolved_now:
        await _save(data)
    return {"resolved_now": resolved_now}


def _brier(probs_outcomes: list[tuple]) -> float | None:
    if not probs_outcomes:
        return None
    return sum((p - o) ** 2 for p, o in probs_outcomes) / len(probs_outcomes)


async def report() -> dict:
    data = await _load()
    bets = data.get("bets", [])
    resolved = [b for b in bets if b.get("status") == "resolved"]
    open_bets = [b for b in bets if b.get("status") == "open"]
    n = len(resolved)
    if n == 0:
        return {"resolved": 0, "open": len(open_bets), "status": "sin datos resueltos todavía",
                "criteria": _criteria_block(None)}
    wins = sum(1 for b in resolved if b.get("won"))
    total_stake = sum(b["stake"] for b in resolved)
    total_pnl = sum(b["pnl"] for b in resolved)
    rois = [(b["pnl"] / b["stake"]) for b in resolved if b.get("stake")]
    net_rois = [r - FEE_HAIRCUT for r in rois]   # haircut per trade
    mean_net = sum(net_rois) / len(net_rois)
    se = (sum((r - mean_net) ** 2 for r in net_rois) / (len(net_rois) - 1)) ** 0.5 / math.sqrt(len(net_rois)) if len(net_rois) > 1 else float("inf")
    ci_low = mean_net - 1.96 * se
    model_brier = _brier([(b["model_prob_yes"], b["outcome_yes"]) for b in resolved])
    market_brier = _brier([(b["implied_prob_yes"], b["outcome_yes"]) for b in resolved])
    summary = {
        "resolved": n, "open": len(open_bets), "wins": wins,
        "hit_rate_pct": round(wins / n * 100, 1),
        "total_stake": round(total_stake, 2), "total_pnl": round(total_pnl, 2),
        "roi_pct": round(total_pnl / total_stake * 100, 2) if total_stake else 0,
        "mean_net_roi_per_bet_pct": round(mean_net * 100, 2),
        "net_roi_ci95_low_pct": round(ci_low * 100, 2),
        "model_brier": round(model_brier, 4) if model_brier is not None else None,
        "market_brier": round(market_brier, 4) if market_brier is not None else None,
        "fee_haircut_per_trade": FEE_HAIRCUT,
    }
    summary["criteria"] = _criteria_block(summary)
    return summary


def _short_label(b: dict) -> str:
    sym = (b.get("symbol") or "").replace("USDT", "")
    tgt = b.get("target") or 0
    tgt_s = f"{tgt/1000:.0f}k" if tgt >= 1000 else (f"{tgt:.0f}" if tgt >= 1 else f"{tgt:.3f}")
    arrow = "≥" if b.get("direction") == "above" else "≤"
    return f"{sym}{arrow}{tgt_s}"[:13]


async def telegram_digest() -> str:
    """Self-explanatory, clean HTML digest for Telegram. Defines every term inline."""
    from app.services.notifications.telegram import html_escape
    rep = await report()
    data = await _load()
    open_bets = [b for b in data.get("bets", []) if b.get("status") == "open"]

    lines = [
        "🧪 <b>Lab Polymarket</b> · paper-trading (sin dinero real)",
        "<i>Apuesto en PAPEL cuando mi modelo de probabilidad discrepa del precio del "
        "mercado. Meta: probar si acierto MÁS que el mercado antes de arriesgar 1€.</i>",
        "━━━━━━━━━━━━━━",
    ]

    n = rep.get("resolved", 0)
    lines.append(f"📊 <b>Resultados</b> — apuestas cerradas: <b>{n}</b>")
    if n == 0:
        lines.append("<i>Aún sin mercados resueltos (tardan semanas en cerrar). "
                     "Que no haya resultados todavía es lo correcto, no un fallo.</i>")
    else:
        beat = (rep.get("model_brier") is not None and rep.get("market_brier") is not None
                and rep["model_brier"] < rep["market_brier"])
        lines += [
            f"• Aciertos: <b>{rep['wins']}/{n}</b> ({rep['hit_rate_pct']}%)",
            f"• Rentabilidad neta: <b>{rep['mean_net_roi_per_bet_pct']:+}%</b> por apuesta "
            f"(IC95 desde {rep['net_roi_ci95_low_pct']:+}%)",
            f"• P&amp;L acumulado: <b>{rep['total_pnl']:+} </b>(papel)",
            f"• ¿Mi modelo predice mejor que el mercado? <b>{'SÍ ✅' if beat else 'NO ❌'}</b> "
            f"<i>(error Brier {rep['model_brier']} vs {rep['market_brier']}; menor = mejor)</i>",
        ]

    if open_bets:
        rows = sorted(open_bets, key=lambda b: abs(b.get("edge") or 0), reverse=True)[:6]
        tbl = [f"{'MERCADO':<13}{'MODELO':>7}{'MERC.':>7}{'VOY':>5}"]
        for b in rows:
            mp = f"{(b.get('model_prob_yes') or 0)*100:.0f}%"
            ip = f"{(b.get('implied_prob_yes') or 0)*100:.0f}%"
            tbl.append(f"{_short_label(b):<13}{mp:>7}{ip:>7}{b.get('side',''):>5}")
        lines += ["", f"🎯 <b>Apuestas abiertas: {len(open_bets)}</b> "
                  "<i>(modelo = mi prob.; merc. = prob. del mercado; voy = a qué lado apuesto)</i>",
                  "<pre>" + html_escape("\n".join(tbl)) + "</pre>"]

    crit = rep.get("criteria", {})
    ready = crit.get("passed")
    lines += ["", f"🚦 <b>¿Listo para dinero real?</b> {'SÍ ✅' if ready else 'NO ❌'}"]
    if not ready:
        lines.append(f"<i>Faltan datos. Bar: ≥{MIN_RESOLVED} cerradas, batir al mercado, y "
                     "rentabilidad neta positiva con significancia. Hasta entonces, solo papel.</i>")
    return "\n".join(lines)


def _criteria_block(s: dict | None) -> dict:
    if not s:
        return {"min_resolved": MIN_RESOLVED, "passed": False,
                "note": f"Necesita ≥{MIN_RESOLVED} apuestas resueltas; aún no hay datos."}
    checks = {
        "sample_ok": s["resolved"] >= MIN_RESOLVED,
        "beats_market_calibration": (s["model_brier"] is not None and s["market_brier"] is not None
                                     and s["model_brier"] < s["market_brier"]),
        "net_roi_ci_positive": s["net_roi_ci95_low_pct"] > 0,
        "cumulative_positive": s["total_pnl"] > 0,
    }
    return {**checks, "passed": all(checks.values()),
            "verdict": ("APTO para piloto mínimo real" if all(checks.values())
                        else "NO apto todavía — sigue en paper")}
