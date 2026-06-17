"""Render the portfolio as a clean, aligned monospace TABLE for Telegram.

The user prefers a tidy text table (bold headline + <pre> grid) over a chart.
Headline stats are recomputed from the SHOWN positions only, so excluded dust
doesn't distort them (per-position fx via market_value_base / market_value)."""

from __future__ import annotations

_NICE = {
    "IE00B4ND3602": "Oro", "IE00BYX5NX33": "MSCI World", "LYX0F.DE": "Nasdaq100",
    "VVSM.DE": "Semis", "QDVF.DE": "Energia", "NUKL.DE": "Uranio", "BTEC.L": "Biotech",
    "COPX.L": "Cobre", "JEDI.DE": "Espacio", "PLTR": "Palantir", "SPCX": "SpaceX",
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "DOGE": "Doge", "PEPE": "Pepe",
}


def _short(pos: dict) -> str:
    t = (pos.get("ticker") or "").upper()
    nm = _NICE.get(t) or (pos.get("name") or t)
    return nm.replace("&", "y")[:10]


def build_summary_html(p: dict, excluded: set[str]) -> str:
    positions = [x for x in p.get("positions", []) if (x.get("ticker") or "").upper() not in excluded]
    if not positions:
        return "💼 <b>Tu cartera</b>: sin posiciones para mostrar."

    def _to_base(pos: dict, field: str) -> float:
        mv = pos.get("market_value") or 0
        fx = (pos["market_value_base"] / mv) if mv else 1.0
        return (pos.get(field) or 0) * fx

    cur = p.get("base_currency", "EUR")
    total = sum(x.get("market_value_base", 0) for x in positions)
    cost = sum(_to_base(x, "cost_basis") for x in positions)
    daily = sum(_to_base(x, "day_change") for x in positions)
    pl = total - cost
    pl_pct = (pl / cost * 100) if cost > 0 else 0.0
    daily_pct = (daily / (total - daily) * 100) if (total - daily) > 0 else 0.0
    trend = "📈" if daily >= 0 else "📉"

    rows = sorted(positions, key=lambda x: (x.get("day_change_pct") or 0), reverse=True)[:14]
    W = 31
    body = [f"{'ACTIVO':<10}{'HOY':>7}{'P/L':>8}{'€':>6}", "─" * W]
    for x in rows:
        d = f"{(x.get('day_change_pct') or 0):+.1f}%"
        pls = f"{(x.get('gain_loss_pct') or 0):+.1f}%"
        val = f"{(x.get('market_value_base') or 0):.0f}€"
        body.append(f"{_short(x):<10}{d:>7}{pls:>8}{val:>6}")
    body.append("─" * W)
    body.append(f"{'TOTAL':<10}{f'{daily_pct:+.1f}%':>7}{f'{pl_pct:+.1f}%':>8}{f'{total:.0f}€':>6}")

    from app.services.notifications.telegram import html_escape
    head = (f"💼 <b>Tu cartera</b> · {total:.2f} {cur}\n"
            f"{trend} Hoy {daily:+.2f} {cur} ({daily_pct:+.2f}%) · 💰 P/L {pl_pct:+.2f}%")
    msg = head + "\n<pre>" + html_escape("\n".join(body)) + "</pre>"
    if excluded:
        msg += f"\n<i>excl.: {', '.join(sorted(excluded))}</i>"
    return msg
