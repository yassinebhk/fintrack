"""Investment-plan tracker: register named plans (e.g. 'largo plazo' / 'táctico'),
snapshot each holding's entry price today, and later measure how each plan is
performing — objectively, so we can see which thesis pans out. No LLM, pure prices."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from app.services.discovery.market_scanner import MarketScanner

_KEY = "investment_plans"


async def _load() -> dict:
    try:
        from sqlalchemy import select
        from app.db import session_scope
        from app.models import JsonCache
        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _KEY))).scalar_one_or_none()
        return row.payload if row and row.payload else {"plans": []}
    except Exception as exc:
        logger.warning("plans load failed: {}", exc)
        return {"plans": []}


async def _save(payload: dict) -> None:
    from app.db import session_scope, upsert_insert
    from app.models import JsonCache
    stmt = upsert_insert()(JsonCache).values(
        key=_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(index_elements=["key"],
                            set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
    async with session_scope() as s:
        await s.execute(stmt)


async def _last_close(scanner: MarketScanner, ticker: str) -> tuple[float | None, str | None]:
    try:
        hist = await scanner.yahoo.get_history(ticker, period="5d")
        closes = [h["close"] for h in (hist or []) if h.get("close")]
        if closes:
            price = await scanner.yahoo.get_price(ticker)
            cur = (price or {}).get("currency")
            return float(closes[-1]), cur
    except Exception as exc:
        logger.debug("plans price {} failed: {}", ticker, exc)
    return None, None


async def register_plan(name: str, horizon: str, holdings: list[dict], note: str = "") -> dict:
    """holdings: [{ticker, label}]. Snapshots entry price today. Replaces a same-name plan."""
    scanner = MarketScanner()
    today = datetime.now(timezone.utc)
    snap = []
    for h in holdings:
        tk = (h.get("ticker") or "").strip()
        if not tk:
            continue
        price, cur = await _last_close(scanner, tk)
        snap.append({"ticker": tk, "label": h.get("label") or tk,
                     "entry_price": round(price, 4) if price else None,
                     "currency": cur, "entry_date": today.date().isoformat()})
    data = await _load()
    data["plans"] = [p for p in data.get("plans", []) if p.get("name") != name]
    data["plans"].append({"name": name, "horizon": horizon, "note": note,
                          "created_at": today.isoformat(), "holdings": snap})
    await _save(data)
    return {"registered": name, "holdings": snap}


async def add_holding(name: str, ticker: str, label: str = "") -> dict:
    """Append ONE holding to an existing plan, snapshotting only its entry today.
    Preserves the other holdings' original entry prices. Creates the plan if missing."""
    ticker = (ticker or "").strip()
    if not ticker:
        return {"error": "ticker vacío"}
    scanner = MarketScanner()
    today = datetime.now(timezone.utc)
    price, cur = await _last_close(scanner, ticker)
    entry = {"ticker": ticker, "label": label or ticker,
             "entry_price": round(price, 4) if price else None,
             "currency": cur, "entry_date": today.date().isoformat()}
    data = await _load()
    for p in data.get("plans", []):
        if p.get("name") == name:
            if any((h.get("ticker") or "").upper() == ticker.upper() for h in p.get("holdings", [])):
                return {"updated": name, "ticker": ticker, "note": "ya estaba en el plan"}
            p.setdefault("holdings", []).append(entry)
            await _save(data)
            return {"added": ticker, "to": name, "entry": entry}
    # plan inexistente → crearlo con este único holding
    data.setdefault("plans", []).append({"name": name, "horizon": "corto-medio (meses)",
                                         "note": "", "created_at": today.isoformat(),
                                         "holdings": [entry]})
    await _save(data)
    return {"created_plan": name, "added": ticker, "entry": entry}


async def evaluate_plans() -> dict:
    """Current performance of each plan vs entry (per holding + equal-weight plan avg)."""
    scanner = MarketScanner()
    data = await _load()
    out = []
    for p in data.get("plans", []):
        rows, changes = [], []
        for h in p.get("holdings", []):
            cur_price, _ = await _last_close(scanner, h["ticker"])
            chg = None
            if cur_price and h.get("entry_price"):
                chg = round((cur_price - h["entry_price"]) / h["entry_price"] * 100, 2)
                changes.append(chg)
            rows.append({**h, "current_price": round(cur_price, 4) if cur_price else None,
                         "change_pct": chg})
        avg = round(sum(changes) / len(changes), 2) if changes else None
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(p["created_at"])).days
        out.append({"name": p["name"], "horizon": p["horizon"], "note": p.get("note", ""),
                    "created_at": p["created_at"], "days_elapsed": days,
                    "avg_change_pct": avg, "holdings": rows})
    return {"plans": out,
            "disclaimer": "Rendimiento equiponderado desde el registro, en la divisa de cada activo "
                          "(sin ajustar por FX ni por DCA). Mide si la tesis se cumple, no es recomendación."}
