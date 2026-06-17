"""Position sizing — turn a basket of picks into risk-managed weights.

Inverse-volatility (a.k.a. naive risk-parity) is the default: it equalizes each
position's risk contribution, which is robust and avoids the estimation-error
blow-ups of full mean-variance optimization with noisy inputs.
"""

from __future__ import annotations


def inverse_vol_weights(vols: dict[str, float], max_weight: float = 0.25) -> dict[str, float]:
    """Weights ∝ 1/vol, normalized to sum 1, with a per-name cap (excess redistributed)."""
    usable = {t: v for t, v in vols.items() if v and v > 0}
    if not usable:
        # equal weight fallback
        n = len(vols) or 1
        return {t: round(1.0 / n, 4) for t in vols}
    raw = {t: 1.0 / v for t, v in usable.items()}
    s = sum(raw.values())
    w = {t: r / s for t, r in raw.items()}
    # apply cap iteratively, redistributing excess to uncapped names
    for _ in range(10):
        over = {t: x for t, x in w.items() if x > max_weight + 1e-9}
        if not over:
            break
        excess = sum(x - max_weight for x in over.values())
        for t in over:
            w[t] = max_weight
        free = [t for t in w if t not in over]
        if not free:
            break
        fs = sum(w[t] for t in free) or 1.0
        for t in free:
            w[t] += excess * (w[t] / fs)
    total = sum(w.values()) or 1.0
    return {t: round(x / total, 4) for t, x in w.items()}
