"""Intraday 'trading pulse'.

A compact snapshot of how the user's real holdings are moving TODAY, pushed a
couple of times a day so short-term decisions (add / trim) have fresh context.
Reuses PortfolioService.calculate_portfolio (live prices + per-position day
change already computed there) and honours the report-excluded dust list so tiny
crypto leftovers don't dominate with their huge % swings.

This is intentionally read-only and opinion-free: it reports the moves, it does
NOT tell the user to buy or sell (consistent with the project's anti-noise,
data-driven philosophy).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from app.config import get_settings
from app.services import report_prefs
from app.services.notifications.telegram import html_escape as _esc
from app.services.portfolio import PortfolioService

# Only surface positions whose move today is at least this big (in %), to keep the
# message signal-dense on calm days.
MOVE_THRESHOLD = 1.0

# Public app URL — the frontend hash router opens #asset/<ticker> (asset detail)
# and #<page> (e.g. #dashboard) from these deep-links.
APP_URL = "https://personalfintrack.duckdns.org"


def _fmt_eur(v: float) -> str:
    """1234.5 -> '1.234' (ES thousands separator, no decimals)."""
    return f"{v:,.0f}".replace(",", ".")


async def build_pulse_html(user_id: int) -> str | None:
    """Build the Telegram HTML for the intraday pulse, or None if there's nothing
    worth sending (no portfolio / prices unavailable)."""
    try:
        data = await PortfolioService(user_id).calculate_portfolio()
    except Exception as exc:
        logger.warning("pulse: portfolio calc failed: {}", exc)
        return None

    positions = data.get("positions") or []
    if not positions:
        return None

    excluded = await report_prefs.get_excluded(user_id)
    positions = [p for p in positions if str(p.get("ticker", "")).upper() not in excluded]
    if not positions:
        return None

    now = datetime.now(ZoneInfo(get_settings().timezone)).strftime("%H:%M")
    day_pct = data.get("daily_change_pct", 0.0) or 0.0
    day_eur = data.get("daily_change", 0.0) or 0.0
    total = data.get("total_value", 0.0) or 0.0
    arrow = "🟢" if day_pct >= 0 else "🔴"

    lines = [
        f"⚡ <b>Pulso de mercado · {now}</b>",
        f"{arrow} Cartera hoy: <b>{day_pct:+.2f}%</b> ({day_eur:+.2f} €) · total {_fmt_eur(total)} €",
    ]

    movers = [p for p in positions if abs(p.get("day_change_pct") or 0) >= MOVE_THRESHOLD]
    ups = sorted((p for p in movers if (p.get("day_change_pct") or 0) > 0),
                 key=lambda p: p.get("day_change_pct") or 0, reverse=True)[:6]
    downs = sorted((p for p in movers if (p.get("day_change_pct") or 0) < 0),
                   key=lambda p: p.get("day_change_pct") or 0)[:6]

    def row(p: dict) -> str:
        tk = str(p.get("ticker") or "")
        # Show a name the user recognizes (not the raw ISIN/ticker), linked to the
        # asset's detail page in the app.
        name = (p.get("name") or tk).strip()
        disp = tk if name.upper() == tk.upper() else name
        disp = (disp[:26] + "…") if len(disp) > 27 else disp
        label = f'<a href="{APP_URL}/#asset/{_esc(tk)}">{_esc(disp)}</a>' if tk else _esc(disp)
        cur = p.get("currency") or ""
        price = p.get("current_price")
        price_txt = f"{price:.2f} {cur}".strip() if price is not None else ""
        return f"• {label} <b>{(p.get('day_change_pct') or 0):+.2f}%</b>" + (f" · {_esc(price_txt)}" if price_txt else "")

    if ups:
        lines.append("\n<b>📈 Suben:</b>")
        lines += [row(p) for p in ups]
    if downs:
        lines.append("\n<b>📉 Bajan:</b>")
        lines += [row(p) for p in downs]
    if not ups and not downs:
        lines.append(f"\nSesión tranquila: nada se mueve más de ±{MOVE_THRESHOLD:.0f}% hoy.")

    lines.append(f'\n🔎 <a href="{APP_URL}/#dashboard">Ver toda tu cartera →</a>')
    lines.append("<i>Solo el movimiento del día — no es una recomendación. Decide con tu plan.</i>")
    return "\n".join(lines)
