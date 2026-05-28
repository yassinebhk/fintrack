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

from loguru import logger
from sqlalchemy import select

from app.db import session_scope
from app.models import RecommendationTrack
from app.services.asset_analysis import _benchmark_for
from app.services.discovery.market_scanner import MarketScanner

_HORIZONS = {"ret_1m": 30, "ret_3m": 90, "ret_6m": 180}
_EXCESS = {"ret_1m": "excess_1m", "ret_3m": "excess_3m", "ret_6m": "excess_6m"}


async def _last_close(scanner: MarketScanner, ticker: str) -> float | None:
    """Most recent close from Yahoo daily history (consistent price source)."""
    try:
        hist = await scanner.yahoo.get_history(ticker, period="1mo")
        closes = [h["close"] for h in (hist or []) if h.get("close")]
        return float(closes[-1]) if closes else None
    except Exception as exc:
        logger.debug("scorecard: price {} failed: {}", ticker, exc)
        return None


async def snapshot_recommendations(payload: dict) -> int:
    """Persist today's opportunities for forward tracking. Idempotent per day."""
    opps = payload.get("opportunities") or []
    if not opps:
        return 0
    scanner = MarketScanner()
    today = datetime.now(timezone.utc).date()
    saved = 0

    async with session_scope() as s:
        for op in opps:
            ticker = (op.get("ticker_or_isin") or "").strip().upper()
            if not ticker:
                continue
            # Skip if we already snapshotted this ticker today.
            existing = (await s.execute(
                select(RecommendationTrack).where(
                    RecommendationTrack.rec_date == today,
                    RecommendationTrack.ticker == ticker,
                )
            )).scalar_one_or_none()
            if existing:
                continue

            price = await _last_close(scanner, ticker)
            if not price:
                continue
            bench_ticker, _ = _benchmark_for(ticker, op.get("kind", ""), "")
            bench_price = await _last_close(scanner, bench_ticker)
            scores = op.get("scores") or {}
            s.add(RecommendationTrack(
                rec_date=today,
                ticker=ticker,
                name=op.get("name", "")[:128],
                approach=op.get("approach", "")[:16],
                conviction=op.get("conviction", "")[:16],
                momentum_score=scores.get("momentum_score"),
                value_score=scores.get("value_score"),
                price_at_rec=price,
                benchmark_ticker=bench_ticker,
                bench_price_at_rec=bench_price,
            ))
            saved += 1
    logger.info("scorecard: snapshotted {} recommendations", saved)
    return saved


async def evaluate_due() -> int:
    """Fill forward returns for snapshots that have reached each horizon."""
    scanner = MarketScanner()
    today = datetime.now(timezone.utc).date()
    updated = 0

    async with session_scope() as s:
        rows = (await s.execute(select(RecommendationTrack))).scalars().all()
        # Cache current prices per ticker so we don't refetch within one run.
        price_cache: dict[str, float | None] = {}

        async def cur(tk: str) -> float | None:
            if tk not in price_cache:
                price_cache[tk] = await _last_close(scanner, tk)
            return price_cache[tk]

        for r in rows:
            age_days = (today - r.rec_date).days
            for field, horizon_days in _HORIZONS.items():
                if getattr(r, field) is not None:
                    continue  # already evaluated
                if age_days < horizon_days:
                    continue  # not due yet
                if not r.price_at_rec:
                    continue
                now_price = await cur(r.ticker)
                if not now_price:
                    continue
                fwd = (now_price - r.price_at_rec) / r.price_at_rec * 100
                setattr(r, field, round(fwd, 2))
                # Excess vs benchmark (alpha), if we have benchmark prices.
                if r.benchmark_ticker and r.bench_price_at_rec:
                    bnow = await cur(r.benchmark_ticker)
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
        "note": (
            "Rendimiento de las ideas DESPUÉS de recomendarlas (out-of-sample). "
            "'alpha_vs_benchmark' = exceso sobre su índice de referencia. "
            "Necesita semanas/meses de historial para ser significativo."
        ),
    }
