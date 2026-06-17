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
    """Apply sleeve caps (crypto, thematic). Per-name cap is handled in sizing."""
    w = cap_sleeve(weights, meta, "crypto", MAX_CRYPTO_SLEEVE)
    w = cap_sleeve(w, meta, "equity_theme", MAX_THEME_SLEEVE)
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
