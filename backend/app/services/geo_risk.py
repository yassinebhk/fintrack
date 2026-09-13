"""Maritime-chokepoint / oil supply-shock radar + second-order exposure map.

A supply shock — a threat to a shipping chokepoint (Hormuz, Bab el-Mandeb/Red
Sea, Suez, Malacca, Bosphorus, Panama), an OPEC+ cut, a tanker/pipeline attack,
an embargo — spikes oil AND drags a predictable set of OTHER assets with it. The
news sentiment classifier tends to read a diplomatic-sounding chokepoint headline
as 'neutral' (that's how "Iran Seeks Gulf Support for Hormuz Plan" slipped
through), so this layer flags it explicitly as a RISK and spells out the knock-on
effects, so the user isn't blindsided.

This is a CURATED HEURISTIC, clearly labelled as such — it powers an alert and
context, it NEVER changes the quant ensemble ranking (see rigor_no_false_positives).
"""

from __future__ import annotations

import re

# --- Detection ---------------------------------------------------------------

# Shipping chokepoints (EN + ES). A mention in financial news is almost always
# supply-risk relevant.
_CHOKEPOINT_TERMS = [
    "hormuz", "ormuz", "bab el-mandeb", "bab-el-mandeb", "bab el mandeb", "mandeb",
    "red sea", "mar rojo", "suez", "malacca", "malaca", "bosphorus", "bósforo",
    "dardanelles", "dardanelos", "strait of", "estrecho de", "chokepoint",
]
# Oil supply-shock terms that are inherently risk-bearing even without a chokepoint.
_SUPPLY_SHOCK_TERMS = [
    "opec cut", "opec+ cut", "opec production cut", "recorte de la opep", "opep recorta",
    "oil embargo", "embargo petrol", "crude embargo", "tanker attack", "tanker seized",
    "petrolero atacado", "ataque petrolero", "houthi", "hut[ií]", "pipeline attack",
    "ataque al oleoducto", "oil blockade", "bloqueo petrol", "supply disruption", "oil sanctions",
    "sanciones al petról",
]

_CHOKEPOINT_RE = re.compile("|".join(re.escape(t) for t in _CHOKEPOINT_TERMS), re.I)
_SHOCK_RE = re.compile("|".join(_SUPPLY_SHOCK_TERMS), re.I)

# Friendly name per chokepoint, for the alert headline.
_CHOKEPOINT_NAMES = {
    "hormuz": "Ormuz", "ormuz": "Ormuz",
    "mandeb": "Bab el-Mandeb", "red sea": "Mar Rojo", "mar rojo": "Mar Rojo",
    "suez": "Suez", "malacca": "Malaca", "malaca": "Malaca",
    "bosphorus": "Bósforo", "bósforo": "Bósforo",
    "dardanelles": "Dardanelos", "dardanelos": "Dardanelos",
}


def _text(item: dict) -> str:
    return f"{item.get('title', '') or ''} {item.get('summary', '') or ''}"


def _chokepoint_of(text: str) -> str | None:
    low = text.lower()
    for key, name in _CHOKEPOINT_NAMES.items():
        if key in low:
            return name
    return None


def detect(news_items: list[dict]) -> list[dict]:
    """Return the subset of headlines that signal an oil supply / chokepoint risk,
    each annotated with the chokepoint name when identifiable."""
    hits: list[dict] = []
    for it in news_items or []:
        text = _text(it)
        if _CHOKEPOINT_RE.search(text) or _SHOCK_RE.search(text):
            hits.append({**it, "chokepoint": _chokepoint_of(text)})
    return hits


# --- Second-order exposure ---------------------------------------------------

SECOND_ORDER_NOTE = (
    "Un shock de petróleo no solo mueve el crudo:\n"
    "👍 Suelen subir: energía/petroleras, refineras, oro y defensivas.\n"
    "👎 Suelen sufrir: aerolíneas y transporte (combustible), consumo, "
    "industriales intensivos en energía y bonos largos (inflación); "
    "y presiona a la renta variable amplia."
)

# Curated keyword buckets to tag a HELD position's likely reaction (heuristic).
_WINNER_TERMS = [
    "oil", "crude", "petrol", "petról", "energy", "energ", "xle", "uso", "bno",
    "exxon", "xom", "chevron", "cvx", "shell", "bp", "total", "totalenergies",
    "repsol", "conoco", "occidental", "oxy", "valero", "vlo", "marathon",
    "halliburton", "schlumberger", "gold", "oro", "gld", "sgld", "iau", "silver",
    "plata", "mining", "miner", "commodit", "materia prima", "utilit", "utili",
]
_LOSER_TERMS = [
    "airline", "aerol", "jets", "ryanair", "iag", "easyjet", "lufthansa", "delta air",
    "united air", "american air", "cruise", "carnival", "travel", "viaje",
    "transport", "logist", "freight", "shipping", "consumer discretion",
    "consumo", "retail", "auto", "automóvil", "chemical", "químic", "industrial",
]
_BROAD_EQUITY_TERMS = [
    "msci world", "all-world", "all world", "ftse all", "s&p 500", "sp500", "s&p500",
    "nasdaq", "world", "acwi", "stoxx", "eurostoxx", "euro stoxx", "total market",
    "global equity", "índice", "index",
]
_LONG_BOND_TERMS = [
    "treasury", "tesoro", "20+", "10+", "long bond", "bono largo", "aggregate",
    "govie", "gilt", "bund", "duration larga",
]


def _pos_text(pos: dict) -> str:
    return f"{pos.get('name', '') or ''} {pos.get('ticker', '') or ''}".lower()


def classify_position(pos: dict) -> tuple[str, str] | None:
    """Return (direction, reason) for a held position under an oil spike, or None
    if it's judged neutral. direction ∈ {'beneficiado','presionado'}."""
    text = _pos_text(pos)
    ptype = (pos.get("type") or "").lower()

    if any(t in text for t in _WINNER_TERMS):
        return ("beneficiado", "energía/oro/materias primas")
    if any(t in text for t in _LOSER_TERMS):
        return ("presionado", "coste de combustible / demanda")
    if any(t in text for t in _LONG_BOND_TERMS):
        return ("presionado", "inflación golpea a los bonos largos")
    if any(t in text for t in _BROAD_EQUITY_TERMS):
        return ("presionado", "presión indirecta en la RV amplia (inflación)")
    if ptype in ("fund", "etf") and any(t in text for t in _BROAD_EQUITY_TERMS):
        return ("presionado", "presión indirecta en la RV amplia (inflación)")
    return None


def exposure(positions: list[dict]) -> dict[str, list[dict]]:
    """Split held positions into likely winners / losers under an oil spike.
    Returns {'beneficiado': [...], 'presionado': [...]} (neutrals omitted)."""
    out: dict[str, list[dict]] = {"beneficiado": [], "presionado": []}
    for pos in positions or []:
        res = classify_position(pos)
        if not res:
            continue
        direction, reason = res
        out[direction].append({
            "ticker": pos.get("ticker"),
            "name": pos.get("name") or pos.get("ticker"),
            "reason": reason,
        })
    return out
