"""Superinvestor holdings — public 13F snapshots of top value managers (Buffett,
Li Lu, Markel, Magallanes) exposed as a browsable idea pool for the web UI.

Long-term VALUE ideas, not short-term trades (13F is a quarterly buy-and-hold
snapshot). Read-only: reuses the same MarketScanner._superinvestor_candidates()
that feeds the opportunity scanner; cached in-process 6h so the Dataroma fetch
isn't hit on every page open."""

import re
import time

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/superinvestors", tags=["superinvestors"])

# Short plain-language "who is this" per manager (shown as the card subtitle).
_ABOUT = {
    "Warren Buffett (Berkshire Hathaway)": "Leyenda del value a largo plazo. Aviso: acaba de dejar todos sus cargos ejecutivos (CEO en ene-2026, presidente el 18-sep-2026), por primera vez en 60 años. Fuente: informes 13F (SEC, públicos).",
    "Li Lu (Himalaya Capital)": "Value muy concentrado y con muy buenos números recientes; vista PARCIAL — el 13F no capta sus posiciones en China/Hong Kong. Munger lo consideraba uno de los mejores inversores que conoció.",
    "Tom Gayner (Markel)": "El más 'sin drama' del grupo: +13,9% el último año, sin escándalos. Compounder diversificado, estilo Berkshire dentro de una aseguradora.",
    "Magallanes (Iván Martín)": "Value ibérico/europeo: 10,27%/año a 10 años, sin ningún año muy malo (2022 fue solo −1,81%). Sin feed en vivo (snapshot manual; España no tiene equivalente al 13F).",
}
_WEIGHT_RE = re.compile(r"([\d.]+)\s*%\s*\)?\s*$")

_CACHE: dict = {"ts": 0.0, "data": None}
_TTL = 6 * 3600  # 6h — Dataroma updates slowly (quarterly 13F filings)


@router.get("")
async def list_superinvestors(current_user: User = Depends(get_current_user)) -> dict:
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["ts"]) < _TTL:
        return _CACHE["data"]

    from app.services.discovery.market_scanner import MarketScanner
    cands = await MarketScanner()._superinvestor_candidates()

    groups: dict[str, list] = {}
    for ticker, info in cands.items():
        cat = info.get("cat", "")  # "gestora · <Manager>"
        manager = cat.split("·", 1)[1].strip() if "·" in cat else (cat or "Otros")
        raw = info.get("name", ticker)
        clean = (raw.split(" (")[0].strip() or ticker)  # company name before the "(Manager, w%)" suffix
        m = _WEIGHT_RE.search(raw)
        weight = round(float(m.group(1)), 2) if m else None
        groups.setdefault(manager, []).append({"ticker": ticker, "name": clean, "weight": weight})

    managers = []
    for manager, holds in groups.items():
        # Highest-conviction (biggest weight) first; unweighted (Magallanes) keep order.
        holds.sort(key=lambda h: (h["weight"] is None, -(h["weight"] or 0.0)))
        managers.append({
            "name": manager,
            "about": _ABOUT.get(manager, ""),
            "count": len(holds),
            "holdings": holds,
        })
    # Most concentrated managers first (fewer positions = higher conviction signal).
    managers.sort(key=lambda mgr: mgr["count"])

    out = {"managers": managers, "total": sum(m["count"] for m in managers)}
    _CACHE.update(ts=now, data=out)
    return out
