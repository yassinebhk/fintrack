"""Target asset-allocation by block + drift vs the live portfolio.

Blocks:
- nucleo      broad, diversified equity core (World, Nasdaq-100, ...)
- oro         gold / safe-haven
- tematico    sector & single-stock tactical bets
- cripto      crypto
- estabilidad cash-like / short bonds (the stability sleeve)

Targets are user-set percentages (JsonCache-backed, defaults below). The daily
summary flags DRIFT (real vs target) so the user rebalances with NEW money
instead of chasing winners or averaging down into losers (disposition effect)."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

_KEY = "allocation_targets"

BLOCKS = ["nucleo", "oro", "tematico", "cripto", "estabilidad"]

BLOCK_LABEL = {
    "nucleo": "Núcleo",
    "oro": "Oro",
    "tematico": "Temático",
    "cripto": "Cripto",
    "estabilidad": "Estable",
}

# Balanced reference split for an aggressive-but-with-a-net profile (sums to 100).
_DEFAULT_TARGETS = {"nucleo": 40, "oro": 10, "tematico": 20, "cripto": 15, "estabilidad": 15}

# Explicit block per known ticker/ISIN (covers the current portfolio + likely adds).
_BLOCK_BY_TICKER = {
    "IE00BYX5NX33": "nucleo",   # MSCI World
    "LYX0F.DE": "nucleo",       # Amundi Core Nasdaq-100
    "IE00B4ND3602": "oro",      # iShares Physical Gold
    "VVSM.DE": "tematico", "QDVF.DE": "tematico", "COPX.L": "tematico",
    "BTEC.L": "tematico", "PLTR": "tematico", "SPCX": "tematico",
    "NUKL.DE": "tematico", "JEDI.DE": "tematico",
    "BTC": "cripto", "ETH": "cripto", "SOL": "cripto", "DOGE": "cripto", "PEPE": "cripto",
    "USPY.DE": "tematico",  # ciberseguridad
    # stability sleeve — cash-like money market + investment-grade bonds
    "XEON.DE": "estabilidad", "PR1R.DE": "estabilidad", "ERNE.DE": "estabilidad",
    "IEAA.L": "estabilidad",  # iShares Core € Corp Bond (IG)
}
_CRYPTO_HINT = {"BTC", "ETH", "SOL", "DOGE", "PEPE", "ADA", "XRP", "BNB", "AVAX", "LTC", "DOT", "LINK", "TRX"}


def classify(ticker: str | None) -> str:
    """Map a ticker/ISIN to its block. Unknown symbols default to 'tematico'
    (except obvious crypto tickers), so a new tactical bet is counted, not hidden."""
    t = (ticker or "").upper()
    if t in _BLOCK_BY_TICKER:
        return _BLOCK_BY_TICKER[t]
    if t in _CRYPTO_HINT:
        return "cripto"
    return "tematico"


async def get_targets() -> dict:
    """User target % per block (defaults to the balanced reference split if unset)."""
    try:
        from sqlalchemy import select

        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        vals = (row.payload or {}).get("targets") if row and row.payload else None
        if vals:
            return {b: float(vals.get(b, 0)) for b in BLOCKS}
    except Exception as exc:
        logger.warning("allocation targets load failed: {}", exc)
    return dict(_DEFAULT_TARGETS)


async def set_targets(targets: dict) -> dict:
    clean = {b: round(float(targets.get(b, 0)), 1) for b in BLOCKS}
    payload = {"targets": clean}
    try:
        from app.db import session_scope, upsert_insert
        from app.models import JsonCache
        stmt = upsert_insert()(JsonCache).values(
            key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(index_elements=["key"],
                                set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
        async with session_scope() as s:
            await s.execute(stmt)
    except Exception:
        logger.exception("allocation targets save failed")
        raise
    return clean


def block_weights(positions: list[dict]) -> tuple[dict, float]:
    """Sum market_value_base per block over ALL positions (real weights, dust incl.)."""
    agg = {b: 0.0 for b in BLOCKS}
    total = 0.0
    for p in positions:
        v = p.get("market_value_base") or 0
        total += v
        agg[classify(p.get("ticker"))] += v
    return agg, total


def format_reparto(positions: list[dict], targets: dict) -> tuple[list[str], str]:
    """Monospace 'objetivo vs real' rows + a one-line rebalance hint.
    `*` = off by ≥5pp, `**` = off by ≥10pp."""
    agg, total = block_weights(positions)
    if total <= 0:
        return [], ""
    lines = [f"{'REPARTO':<9}{'Obj':>4}{'Real':>6}{'Desv':>6}", "─" * 25]
    diffs: dict[str, float] = {}
    for b in BLOCKS:
        tgt = targets.get(b, 0)
        real = agg[b] / total * 100
        diff = real - tgt
        diffs[b] = diff
        flag = "**" if abs(diff) >= 10 else ("*" if abs(diff) >= 5 else "")
        lines.append(f"{BLOCK_LABEL[b]:<9}{f'{tgt:.0f}%':>4}{f'{real:.0f}%':>6}{f'{diff:+.0f}':>6}  {flag}")
    # where to steer NEW money: blocks furthest BELOW target.
    under = sorted((b for b in BLOCKS if diffs[b] <= -5), key=lambda b: diffs[b])
    hint = ""
    if under:
        hint = "Aporta nuevo → " + ", ".join(f"{BLOCK_LABEL[b]} ({diffs[b]:+.0f}pp)" for b in under)
    return lines, hint
