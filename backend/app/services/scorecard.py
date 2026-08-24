"""Out-of-sample scorecard for the recommendation engine.

- snapshot_recommendations(): store each opportunity at the moment it's made,
  with its price and its benchmark's price.
- evaluate_due(): for snapshots that have reached the 1m / 3m / 6m horizon, fetch
  the current prices and record forward return + excess vs benchmark.
- summary(): aggregate hit rate, average forward return and average alpha, broken
  down by horizon, approach and conviction — the honest verdict on the engine.

Prices come from Yahoo daily history (last close), the same source the engine
uses, so snapshot and evaluation are consistent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import median

from loguru import logger
from scipy.stats import ttest_1samp
from sqlalchemy import select

from app.db import session_scope
from app.models import RecommendationTrack
from app.services.asset_analysis import _benchmark_for
from app.services.discovery.market_scanner import MarketScanner

_HORIZONS = {"ret_1m": 30, "ret_3m": 90, "ret_6m": 180}
_EXCESS = {"ret_1m": "excess_1m", "ret_3m": "excess_3m", "ret_6m": "excess_6m"}

# Anti-noise gate for the feedback loop (feedback_context() below): mirrors the
# philosophy of systematic/paper.py's readiness gate (days>=56, marks>=30) but
# adapted for a cross-sectional table (many tickers/dates) rather than one
# sequential NAV curve — n alone isn't enough here, since 30 recommendations
# could all come from one bad week. Both must hold before a bucket is trusted.
MIN_N_FEEDBACK = 30
MIN_SPAN_DAYS_FEEDBACK = 90


def _close_on_or_before(hist: list[dict], target: date) -> float | None:
    """Last close at or before `target` from a Yahoo history list (dates 'YYYY-MM-DD')."""
    chosen = None
    for h in hist or []:
        d = h.get("date")
        c = h.get("close")
        if not d or c is None:
            continue
        if d <= target.isoformat():
            chosen = c
        else:
            break
    return float(chosen) if chosen is not None else None


async def snapshot_recommendations(payload: dict) -> int:
    """Persist today's opportunities for forward tracking — FAST: only ticker, scores
    and benchmark id (no price fetches here, to keep generation off the hot path).
    Baseline and forward prices are derived later by evaluate_due() from history.
    Idempotent per day."""
    opps = payload.get("opportunities") or []
    if not opps:
        return 0
    today = datetime.now(timezone.utc).date()
    saved = 0
    async with session_scope() as s:
        for op in opps:
            ticker = (op.get("ticker_or_isin") or "").strip().upper()
            if not ticker:
                continue
            existing = (await s.execute(
                select(RecommendationTrack).where(
                    RecommendationTrack.rec_date == today,
                    RecommendationTrack.ticker == ticker,
                )
            )).scalar_one_or_none()
            if existing:
                continue
            bench_ticker, _ = _benchmark_for(ticker, op.get("kind", ""), "")
            scores = op.get("scores") or {}
            s.add(RecommendationTrack(
                rec_date=today, ticker=ticker, name=op.get("name", "")[:128],
                approach=op.get("approach", "")[:16], conviction=op.get("conviction", "")[:16],
                momentum_score=scores.get("momentum_score"), value_score=scores.get("value_score"),
                benchmark_ticker=bench_ticker,
            ))
            saved += 1
    logger.info("scorecard: snapshotted {} recommendations (prices backfilled by evaluator)", saved)
    return saved


async def evaluate_due() -> int:
    """Fill baseline price (close on rec_date) + forward returns for snapshots that
    have reached each horizon. One Yahoo history call per ticker (cached per run),
    off the generation hot path."""
    scanner = MarketScanner()
    today = datetime.now(timezone.utc).date()
    updated = 0
    hist_cache: dict[str, list[dict]] = {}

    async def history(tk: str) -> list[dict]:
        if tk not in hist_cache:
            try:
                hist_cache[tk] = await scanner.yahoo.get_history(tk, period="1y") or []
            except Exception:
                hist_cache[tk] = []
        return hist_cache[tk]

    async with session_scope() as s:
        rows = (await s.execute(select(RecommendationTrack))).scalars().all()

        for r in rows:
            age_days = (today - r.rec_date).days
            # Skip rows with no horizon due yet AND nothing to backfill.
            if age_days < min(_HORIZONS.values()) and r.price_at_rec is not None:
                continue

            hist = await history(r.ticker)
            if not hist:
                continue
            # Backfill baseline (close on/before rec_date) and benchmark baseline once.
            if r.price_at_rec is None:
                r.price_at_rec = _close_on_or_before(hist, r.rec_date)
            if r.benchmark_ticker and r.bench_price_at_rec is None:
                bh = await history(r.benchmark_ticker)
                r.bench_price_at_rec = _close_on_or_before(bh, r.rec_date)
            if not r.price_at_rec:
                continue
            now_price = float(hist[-1]["close"]) if hist and hist[-1].get("close") else None
            if not now_price:
                continue

            for field, horizon_days in _HORIZONS.items():
                if getattr(r, field) is not None or age_days < horizon_days:
                    continue
                fwd = (now_price - r.price_at_rec) / r.price_at_rec * 100
                setattr(r, field, round(fwd, 2))
                if r.benchmark_ticker and r.bench_price_at_rec:
                    bh = await history(r.benchmark_ticker)
                    bnow = float(bh[-1]["close"]) if bh and bh[-1].get("close") else None
                    if bnow:
                        bfwd = (bnow - r.bench_price_at_rec) / r.bench_price_at_rec * 100
                        setattr(r, _EXCESS[field], round(fwd - bfwd, 2))
                updated += 1
    logger.info("scorecard: evaluated {} horizon points", updated)
    return updated


def _agg(values: list[float]) -> dict | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    hits = sum(1 for v in vals if v > 0)
    return {
        "n": len(vals),
        "avg": round(sum(vals) / len(vals), 2),
        "hit_rate_pct": round(hits / len(vals) * 100, 1),
        "best": round(max(vals), 2),
        "worst": round(min(vals), 2),
    }


async def summary() -> dict:
    """Aggregate the honest verdict: hit rate + avg return + avg alpha per horizon,
    plus a breakdown by approach and conviction."""
    async with session_scope() as s:
        rows = (await s.execute(select(RecommendationTrack))).scalars().all()

    total = len(rows)
    horizons = {}
    for field, excess in _EXCESS.items():
        ret_stats = _agg([getattr(r, field) for r in rows])
        exc_stats = _agg([getattr(r, excess) for r in rows])
        label = {"ret_1m": "1 mes", "ret_3m": "3 meses", "ret_6m": "6 meses"}[field]
        horizons[field] = {"label": label, "return": ret_stats, "alpha_vs_benchmark": exc_stats}

    # Breakdown by approach / conviction at the 3-month horizon (most meaningful).
    def breakdown(attr: str) -> dict:
        out: dict = {}
        groups: dict[str, list[float]] = {}
        for r in rows:
            key = getattr(r, attr) or "—"
            if r.ret_3m is not None:
                groups.setdefault(key, []).append(r.ret_3m)
        for k, v in groups.items():
            out[k] = _agg(v)
        return out

    return {
        "total_recommendations_tracked": total,
        "evaluated_any": sum(1 for r in rows if r.ret_1m is not None),
        "horizons": horizons,
        "by_approach_3m": breakdown("approach"),
        "by_conviction_3m": breakdown("conviction"),
        "feedback_gate": await feedback_context(rows),
        "note": (
            "Rendimiento de las ideas DESPUÉS de recomendarlas (out-of-sample). "
            "'alpha_vs_benchmark' = exceso sobre su índice de referencia. "
            "Necesita semanas/meses de historial para ser significativo."
        ),
    }


def _bucket_stats(rows: list[RecommendationTrack], attr: str) -> dict:
    """Group by `attr` (approach/conviction) at the 3-month horizon and gate each
    group on (n >= MIN_N_FEEDBACK and date span >= MIN_SPAN_DAYS_FEEDBACK) — the
    anti-noise threshold. Ungated groups still get a real n/span so the caller can
    show honest progress ("12/30"), never silence."""
    groups: dict[str, list[tuple[date, float]]] = {}
    for r in rows:
        if r.ret_3m is not None:
            key = getattr(r, attr) or "—"
            groups.setdefault(key, []).append((r.rec_date, r.ret_3m))

    out: dict = {}
    for key, pairs in groups.items():
        vals = [v for _, v in pairs]
        dates = [d for d, _ in pairs]
        n = len(vals)
        span_days = (max(dates) - min(dates)).days if n > 1 else 0
        p_value = float(ttest_1samp(vals, 0.0).pvalue) if n >= 5 else None
        gated = n >= MIN_N_FEEDBACK and span_days >= MIN_SPAN_DAYS_FEEDBACK
        out[key] = {
            "n": n,
            "n_required": MIN_N_FEEDBACK,
            "span_days": span_days,
            "span_days_required": MIN_SPAN_DAYS_FEEDBACK,
            "median": round(median(vals), 2),
            "hit_rate_pct": round(sum(1 for v in vals if v > 0) / n * 100, 1),
            "p_value": round(p_value, 3) if p_value is not None else None,
            "gated": gated,
            "significant": bool(gated and p_value is not None and p_value < 0.10),
        }
    return out


_feedback_gate_seen_open: set[str] = set()


async def feedback_context(rows: list[RecommendationTrack] | None = None) -> dict:
    """The self-training input: real out-of-sample stats per approach/conviction,
    gated so a small sample never gets used as if it were a real pattern. This is
    read by opportunities.py to (a) hand the LLM real numbers to calibrate
    'conviction' with, and (b) nudge the no-LLM template fallback — but ONLY for
    buckets where `gated` is True. Everything else must be treated as noise."""
    if rows is None:
        async with session_scope() as s:
            rows = (await s.execute(select(RecommendationTrack))).scalars().all()
    fb = {"by_approach": _bucket_stats(rows, "approach"), "by_conviction": _bucket_stats(rows, "conviction")}
    for group_name, buckets in fb.items():
        for key, stats in buckets.items():
            marker = f"{group_name}:{key}"
            if stats["gated"] and marker not in _feedback_gate_seen_open:
                _feedback_gate_seen_open.add(marker)
                logger.info(
                    "scorecard feedback: {} just crossed the anti-noise gate (n={}, span={}d) — "
                    "the self-training loop is now live for this bucket",
                    marker, stats["n"], stats["span_days"],
                )
    return fb


def render_feedback_for_prompt(fb: dict) -> str:
    """Render feedback_context()'s output as prompt text for AnalystAgent. Ungated
    buckets are shown as explicitly insufficient — never silently omitted, so the
    LLM (and anyone reading the raw prompt) sees the same honesty the UI does."""
    lines = [
        "Historial del motor (out-of-sample, usar SOLO para calibrar convicción, NO para elegir tickers):",
    ]
    labels = {"by_approach": "por enfoque", "by_conviction": "por convicción"}
    any_gated = False
    for group_name, buckets in fb.items():
        if not buckets:
            continue
        for key, stats in sorted(buckets.items()):
            tag = f"{key.upper()} ({labels[group_name]})"
            if stats["gated"]:
                any_gated = True
                lines.append(
                    f"- {tag}: n={stats['n']} en {stats['span_days']}d — mediana {stats['median']:+.1f}% a 3m, "
                    f"{stats['hit_rate_pct']:.0f}% de aciertos"
                    + (", diferencia de 0 estadísticamente significativa" if stats["significant"] else ", sin significancia estadística clara")
                    + "."
                )
            else:
                lines.append(f"- {tag}: n={stats['n']}/{stats['n_required']} — insuficiente, sin conclusión.")
    if not any_gated:
        lines.append(
            f"Nota: con <{MIN_N_FEEDBACK} muestras a 3 meses o <{MIN_SPAN_DAYS_FEEDBACK} días de rango, "
            "cualquier patrón es ruido; ignora este bloque por completo."
        )
    return "\n".join(lines)
