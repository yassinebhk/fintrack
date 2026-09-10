"""Risk gates — hard limits a proposed allocation must respect before it's accepted.

These are the difference between "a backtest" and a system you'd trust with money:
position caps, an asset-class sleeve cap (e.g. crypto), and a drawdown circuit
breaker that forces the portfolio to cash when losses breach a threshold.
"""

from __future__ import annotations

# --- limits ---
MAX_WEIGHT_PER_NAME = 0.25       # no single position above 25%
MAX_CRYPTO_SLEEVE = 0.20         # crypto, combined, capped at 20%
MAX_THEME_SLEEVE = 0.60          # thematic/sector bets combined capped at 60%
MAX_SINGLE_STOCK_SLEEVE = 0.40   # all individual stocks combined ≤ 40% — single-name
                                 # (idiosyncratic) risk is real, so cap the sleeve even
                                 # though inverse-vol sizing already down-weights each
DRAWDOWN_CIRCUIT_BREAKER = -0.18  # if paper NAV is >18% below its peak → go to cash


def cap_sleeve(weights: dict[str, float], meta: dict[str, dict],
               asset_class: str, cap: float) -> dict[str, float]:
    """Scale down a whole asset-class sleeve to `cap`, redistributing to the rest."""
    members = [t for t in weights if (meta.get(t, {}).get("asset_class") == asset_class)]
    sleeve = sum(weights[t] for t in members)
    if sleeve <= cap or sleeve <= 0:
        return weights
    scale = cap / sleeve
    out = dict(weights)
    freed = 0.0
    for t in members:
        new = out[t] * scale
        freed += out[t] - new
        out[t] = round(new, 4)
    others = [t for t in out if t not in members]
    os = sum(out[t] for t in others)
    if others and os > 0:
        for t in others:
            out[t] = round(out[t] + freed * (out[t] / os), 4)
    return out


def apply_gates(weights: dict[str, float], meta: dict[str, dict]) -> dict[str, float]:
    """Apply sleeve caps (crypto, thematic, single stocks). Per-name cap is handled
    in sizing.

    Capping one sleeve redistributes its excess to the others, which can push a
    previously-capped sleeve back over its limit — so we iterate to convergence
    (always possible: the uncapped classes — broad/commodity/bond — absorb the
    overflow). Without this, a gate can silently violate its own cap."""
    caps = {"crypto": MAX_CRYPTO_SLEEVE, "equity_theme": MAX_THEME_SLEEVE,
            "equity_single": MAX_SINGLE_STOCK_SLEEVE}
    w = dict(weights)
    for _ in range(8):
        for cls, cap in caps.items():
            w = cap_sleeve(w, meta, cls, cap)
        tot = sum(w.values()) or 1.0
        if all(sum(w[t] for t in w if meta.get(t, {}).get("asset_class") == cls) / tot
               <= cap + 1e-6 for cls, cap in caps.items()):
            break
    total = sum(w.values()) or 1.0
    return {t: round(x / total, 4) for t, x in w.items()}


def drawdown_breached(equity_curve: list[float]) -> bool:
    """True if current NAV is more than the circuit-breaker below its running peak."""
    if not equity_curve:
        return False
    peak = max(equity_curve)
    if peak <= 0:
        return False
    return (equity_curve[-1] / peak - 1.0) <= DRAWDOWN_CIRCUIT_BREAKER
