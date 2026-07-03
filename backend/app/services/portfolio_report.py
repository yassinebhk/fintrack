"""Render the portfolio as a clean, aligned monospace TABLE for Telegram.

The user prefers a tidy text table (bold headline + <pre> grid) over a chart.
Headline stats are recomputed from the SHOWN positions only, so excluded dust
doesn't distort them (per-position fx via market_value_base / market_value)."""

from __future__ import annotations

_PIN_KEY = "pinned_daily_summary"


async def _load_pin() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _PIN_KEY))).scalar_one_or_none()
        return (row.payload or {}) if row and row.payload else {}
    except Exception:
        return {}


async def _save_pin(message_id: int, date: str) -> None:
    from datetime import datetime, timezone
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    payload = {"message_id": message_id, "date": date}
    stmt = upsert_insert()(JsonCache).values(key=_PIN_KEY, payload=payload, updated_at=datetime.now(timezone.utc)) \
        .on_conflict_do_update(index_elements=["key"], set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


async def send_daily_summary_pinned(force: bool = False) -> dict:
    """Build the portfolio table, send it, unpin yesterday's, pin today's.
    Idempotent per day: if already sent today it skips (unless force=True), so several
    morning cron times can fire as redundancy without spamming the user."""
    from datetime import datetime, timezone
    from app.services.notifications.telegram import TelegramNotifier
    from app.services.portfolio import PortfolioService
    from app.services.report_prefs import get_excluded

    today = datetime.now(timezone.utc).date().isoformat()
    prev = await _load_pin()
    if not force and prev.get("date") == today:
        return {"skipped": "ya enviado hoy", "date": today}

    p = await PortfolioService().calculate_portfolio()
    excluded = await get_excluded()
    html = build_summary_html(p, excluded) + "\n📌 <i>Resumen diario</i>"
    n = TelegramNotifier()
    mid = await n.send_html_return_id(html)
    if not mid:
        await n.send_html(html)  # fallback: at least deliver, unpinned
        return {"sent": True, "pinned": False}
    prev_id = prev.get("message_id")
    if prev_id and prev_id != mid:
        await n.unpin_message(prev_id)
    pinned = await n.pin_message(mid)
    await _save_pin(mid, today)
    return {"sent": True, "pinned": pinned, "message_id": mid}


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

    # PUESTO = lo invertido (coste) · AHORA = valor actual · P/L% = ganancia/pérdida.
    rows = sorted(positions, key=lambda x: (x.get("market_value_base") or 0), reverse=True)[:14]
    W = 30
    body = [f"{'ACTIVO':<10}{'PUESTO':>7}{'AHORA':>7}{'P/L':>6}", "─" * W]
    for x in rows:
        put = f"{_to_base(x, 'cost_basis'):.0f}€"
        now = f"{(x.get('market_value_base') or 0):.0f}€"
        pls = f"{(x.get('gain_loss_pct') or 0):+.0f}%"
        body.append(f"{_short(x)[:10]:<10}{put:>7}{now:>7}{pls:>6}")
    body.append("─" * W)
    body.append(f"{'TOTAL':<10}{f'{cost:.0f}€':>7}{f'{total:.0f}€':>7}{f'{pl_pct:+.0f}%':>6}")

    from app.services.notifications.telegram import html_escape
    head = (f"💼 <b>Tu cartera</b> · {total:.2f} {cur}\n"
            f"{trend} Hoy {daily:+.2f} {cur} ({daily_pct:+.2f}%) · 💰 P/L {pl_pct:+.2f}%")
    msg = head + "\n<pre>" + html_escape("\n".join(body)) + "</pre>"
    if excluded:
        msg += f"\n<i>excl.: {', '.join(sorted(excluded))}</i>"
    return msg
