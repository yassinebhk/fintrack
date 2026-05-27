"""'What's working now' analysis — top growers of the last months + the patterns
they share, so discovery can factor in *what kind of asset* is currently winning.

This runs AFTER the ensemble scoring: the quant engine still ranks objectively;
this layer is context. It mines the recent winners for common, human-readable
traits (trend, momentum, volatility band, dominant themes) and measures how much
each candidate resembles that 'winning profile' (winner_affinity).

Honest caveat baked into the output: a strong winning profile is also a
mean-reversion / buy-the-top risk, so it's flagged, never blindly chased.
"""

from collections import Counter
from statistics import median


def _growth(it: dict) -> float | None:
    """Trailing growth: blend 3m (primary) and 6m if available."""
    r3, r6 = it.get("ret_3m"), it.get("ret_6m")
    if r3 is None and r6 is None:
        return None
    if r6 is None:
        return r3
    if r3 is None:
        return r6
    return 0.6 * r3 + 0.4 * r6


def winning_profile(items: list[dict]) -> dict:
    """Average profile of the recent top growers."""
    scored = [(it, _growth(it)) for it in items if _growth(it) is not None and it.get("factors")]
    if len(scored) < 4:
        return {}
    scored.sort(key=lambda x: x[1], reverse=True)
    n_top = max(3, len(scored) // 6)  # top ~15%
    top = [it for it, _ in scored[:n_top]]

    def med(key: str, src: str = "factors") -> float | None:
        vals = [(it.get(src) or {}).get(key) for it in top]
        vals = [v for v in vals if v is not None]
        return round(median(vals), 3) if vals else None

    cats = Counter(it.get("category", "") for it in top if it.get("category"))
    regions = Counter(it.get("region", "") for it in top if it.get("region"))
    pct_above = sum(1 for it in top if (it.get("factors") or {}).get("above_sma200")) / len(top)

    return {
        "n_top": len(top),
        "top_categories": [c for c, _ in cats.most_common(3)],
        "top_regions": [r for r, _ in regions.most_common(2) if r],
        "pct_above_sma200": round(pct_above, 2),
        "median_momentum": med("momentum"),
        "median_sharpe": med("sharpe"),
        "median_vol": med("ewma_vol"),
        "median_range_pos": med("range_pos"),
        "median_rsi": med("rsi", src="signals"),
    }


def winner_affinity(it: dict, profile: dict) -> float:
    """0-1: how much an instrument resembles the current winning profile."""
    if not profile or not it.get("factors"):
        return 0.0
    score = 0.0
    # Shares a dominant winning theme/region
    if it.get("category") in profile.get("top_categories", []):
        score += 0.35
    if it.get("region") and it.get("region") in profile.get("top_regions", []):
        score += 0.15
    # Confirms the trend the winners share
    if profile.get("pct_above_sma200", 0) >= 0.6 and (it["factors"].get("above_sma200")):
        score += 0.30
    # Momentum on the same side as the winners
    mm = profile.get("median_momentum")
    if mm is not None and it["factors"].get("momentum", 0) >= mm * 0.5:
        score += 0.20
    return round(min(score, 1.0), 2)


def analyze_trends(universe_items: list[dict], crypto_items: list[dict] | None = None) -> dict:
    """Top growers + recurring patterns, across ETFs/funds and (optionally) crypto."""
    crypto_items = crypto_items or []
    everything = universe_items + crypto_items

    def top_list(items: list[dict], k: int = 6) -> list[dict]:
        rows = [(it, _growth(it)) for it in items if _growth(it) is not None]
        rows.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "ticker": it.get("ticker"),
                "name": it.get("theme") or it.get("ticker"),
                "ret_3m": it.get("ret_3m"),
                "ret_6m": it.get("ret_6m"),
                "category": it.get("category", ""),
                "above_sma200": bool((it.get("factors") or {}).get("above_sma200")),
            }
            for it, _ in rows[:k]
        ]

    profile = winning_profile(universe_items)
    patterns: list[str] = []
    if profile:
        if profile["pct_above_sma200"] >= 0.8:
            patterns.append(
                f"{profile['pct_above_sma200']:.0%} de los que más suben están sobre su tendencia de "
                "200 sesiones: el dinero premia tendencias ya confirmadas, no rebotes."
            )
        if profile.get("top_categories"):
            patterns.append("Predominan: " + ", ".join(profile["top_categories"]) + ".")
        if profile.get("top_regions"):
            patterns.append("Regiones calientes: " + ", ".join(profile["top_regions"]) + ".")
        rsi = profile.get("median_rsi")
        if rsi is not None and rsi >= 65:
            patterns.append(
                f"RSI medio {rsi:.0f}: muchos ganadores están extendidos/sobrecomprados "
                "(riesgo de comprar caro — vigilar el timing)."
            )
        mm = profile.get("median_momentum")
        if mm is not None:
            patterns.append(f"Momentum medio de los líderes: {mm*100:+.0f}% (multi-periodo).")

    return {
        "top_growers": top_list(everything, k=8),
        "top_growers_etf": top_list(universe_items, k=6),
        "top_growers_crypto": top_list(crypto_items, k=5),
        "profile": profile,
        "patterns": patterns,
    }
