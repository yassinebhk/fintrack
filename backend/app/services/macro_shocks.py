"""Macro-shock radar — multi-domain, second-order aware.

Generalises the oil/chokepoint detector to the other market-moving domains: a
shock rarely stays in its lane, it drags a predictable set of OTHER assets with
it. The news sentiment classifier tends to read these headlines as 'neutral'
(diplomatic/technical phrasing), so this layer flags the shock explicitly and
spells out who tends to win / lose, cross-referencing the user's holdings AND
the day's opportunities.

CURATED HEURISTIC, clearly labelled — powers alerts + context, NEVER changes the
quant ensemble ranking (see rigor_no_false_positives, analysis_must_be_data_driven).

Detection is deliberately conservative (word-boundary + risk-angled phrasing, not
bare topic words) so a normal "oil earnings" or "chip demand" headline does NOT
trip a shock. Each theme carries its own winners/losers map because the same
asset can flip sign by domain (e.g. long bonds: hurt by an inflation shock,
helped by a credit-crisis flight to safety; gold: up in war, down on rising real
yields).
"""

from __future__ import annotations

import re

# Named shipping chokepoints (only the energy theme annotates these).
_CHOKEPOINT_NAMES = {
    "hormuz": "Ormuz", "ormuz": "Ormuz",
    "bab el-mandeb": "Bab el-Mandeb", "bab-el-mandeb": "Bab el-Mandeb", "mandeb": "Bab el-Mandeb",
    "red sea": "Mar Rojo", "mar rojo": "Mar Rojo", "suez": "Suez",
    "malacca": "Malaca", "malaca": "Malaca", "bosphorus": "Bósforo", "bósforo": "Bósforo",
    "dardanelles": "Dardanelos", "taiwan strait": "Estrecho de Taiwán",
}

# Each theme: risk-angled detection terms + a curated winners/losers map.
THEMES: list[dict] = [
    {
        "key": "energia", "name": "oferta de energía (petróleo/gas)", "emoji": "🛢️",
        "detect": [
            "hormuz", "ormuz", "bab el-mandeb", "bab-el-mandeb", "mandeb", "red sea",
            "mar rojo", "suez", "malacca", "malaca", "bosphorus", "strait of", "estrecho de",
            "opec cut", "opec+ cut", "opec production cut", "recorte de la opep", "opep recorta",
            "oil embargo", "crude embargo", "embargo petrol", "oil sanctions", "sanciones al petról",
            "tanker attack", "tanker seized", "petrolero atacado", "pipeline attack",
            "ataque al oleoducto", "oil blockade", "supply disruption", "houthi", "hut[ií]",
            "nord stream", "gas cutoff", "gas cut-off", "corte de gas", "gasoducto",
        ],
        "note": "👍 energía/petroleras/oro · 👎 aerolíneas, transporte, consumo, industriales, bonos largos y RV amplia",
        "winners": ["oil", "crude", "petrol", "petról", "energy", "energ", "xle", "uso", "gas",
                    "exxon", "xom", "chevron", "cvx", "shell", "repsol", "valero", "vlo",
                    "gold", "oro", "gld", "sgld", "mining", "miner", "commodit", "materia prima", "utilit"],
        "losers": ["airline", "aerol", "jets", "ryanair", "iag", "cruise", "travel", "transport",
                   "logist", "shipping", "consum", "retail", "auto", "chemical", "químic", "industrial",
                   "treasury", "bono largo", "20+", "aggregate", "world", "nasdaq", "s&p", "acwi"],
    },
    {
        "key": "chips", "name": "semiconductores (Taiwán/chips)", "emoji": "💽",
        "detect": ["taiwan strait", "taiwan tension", "invade taiwan", "chip ban", "chip curbs",
                   "chip export", "export control", "export curbs", "semiconductor ban",
                   "chip shortage", "escasez de chips", "controles a la exportación",
                   "restrict chip", "tsmc halt", "asml ban"],
        "note": "👍 chips domésticos/defensa/oro · 👎 semiconductores, tecnología, autos y RV amplia",
        "winners": ["intel", "defense", "defensa", "gold", "oro"],
        "losers": ["semiconduct", "chip", "soxx", "smh", "nvidia", "nvda", "amd", "asml", "tsmc",
                   "tech", "tecnolog", "nasdaq", "auto", "automó", "world"],
    },
    {
        "key": "aranceles", "name": "aranceles / guerra comercial", "emoji": "🚧",
        "detect": ["tariff", "aranceles", "trade war", "guerra comercial", "import duties",
                   "import levy", "customs duties", "export ban", "trade barrier", "arancel"],
        "note": "👍 doméstico/oro · 👎 exportadoras, autos, consumo, China/emergentes y RV amplia",
        "winners": ["gold", "oro", "defense", "defensa", "domestic"],
        "losers": ["export", "auto", "automó", "retail", "consum", "china", "emerging", "emergent",
                   "industrial", "semiconduct", "chip", "nasdaq", "world", "acwi", "mchi", "kweb"],
    },
    {
        "key": "tipos", "name": "tipos / inflación (endurecimiento)", "emoji": "📈",
        "detect": ["rate hike", "hike rates", "hawkish", "sticky inflation", "inflation surge",
                   "cpi jump", "hot inflation", "subida de tipos", "tipos más altos", "yields surge",
                   "bond selloff", "tightening", "higher for longer"],
        "note": "👍 banca/valor/energía · 👎 bonos largos, growth/tech, inmobiliario y RV amplia",
        "winners": ["bank", "banc", "financ", "value", "valor", "energy", "energ"],
        "losers": ["treasury", "bono largo", "20+", "long bond", "aggregate", "govie", "growth",
                   "tech", "tecnolog", "nasdaq", "reit", "inmobil", "real estate", "gold", "oro"],
    },
    {
        "key": "geopolitica", "name": "conflicto / geopolítica (risk-off)", "emoji": "⚔️",
        "detect": ["airstrike", "air strike", "missile", "misil", "drone strike", "invasion",
                   "invasión", "military strike", "military operation", "troops", "war", "guerra",
                   "nuclear", "sanctions", "sanciones", "ceasefire collapse", "escalation", "escalada"],
        "note": "👍 defensa/oro/energía · 👎 RV amplia, viajes/aerolíneas, emergentes y cripto",
        "winners": ["defense", "defensa", "gold", "oro", "energy", "energ", "oil", "petrol"],
        "losers": ["airline", "aerol", "travel", "viaje", "emerging", "emergent", "world", "nasdaq",
                   "acwi", "crypto", "bitcoin", "btc", "ether", "eth", "pepe", "doge", "xrp",
                   "ripple", "bnb", "litecoin", "cardano", "memecoin"],
    },
    {
        "key": "credito", "name": "banca / crédito (estrés financiero)", "emoji": "🏦",
        "detect": ["bank failure", "bank collapse", "banking crisis", "credit crunch", "contagion",
                   "bank run", "bailout", "liquidity crisis", "debt default", "quiebra banc",
                   "crisis bancaria", "rescate bancario", "corralito"],
        "note": "👍 oro / bonos refugio / calidad · 👎 bancos, financieras, crédito HY y RV amplia",
        "winners": ["gold", "oro", "treasury", "bono", "quality", "calidad", "utilit"],
        "losers": ["bank", "banc", "financ", "credit", "high yield", "insurance", "seguro",
                   "world", "nasdaq", "s&p", "acwi"],
    },
]


def _compile(terms: list[str]) -> re.Pattern:
    # Word-boundary alternation so "war" doesn't match "warehouse". The optional
    # (?:es|s)? suffix catches plurals (Houthi->Houthis, tariff->tariffs) without
    # re-opening the "war"->"warehouse" false match (the trailing \b still holds).
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")(?:es|s)?\b", re.I)


def _compile_prefix(terms: list[str]) -> re.Pattern:
    # Word-START (prefix) match: a stem like "energ" matches "energy"/"energía"
    # (kept from the intentional stemming) but ONLY at a word boundary, so it does
    # NOT match mid-word (that's what mis-tagged unrelated tickers before).
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")", re.I)


for _t in THEMES:
    _t["_re"] = _compile(_t["detect"])
    _t["_win_re"] = _compile_prefix(_t["winners"])
    _t["_lose_re"] = _compile_prefix(_t["losers"])


def _text(item: dict) -> str:
    return f"{item.get('title', '') or ''} {item.get('summary', '') or ''}"


def _chokepoint_of(text: str) -> str | None:
    low = text.lower()
    for key, name in _CHOKEPOINT_NAMES.items():
        if key in low:
            return name
    return None


def active_shocks(news_items: list[dict], per_theme: int = 3) -> list[dict]:
    """Return the active shock themes in today's headlines. Each entry:
    {key, name, emoji, note, chokepoint?, hits: [top headlines]}."""
    out: list[dict] = []
    for theme in THEMES:
        hits = [it for it in (news_items or []) if theme["_re"].search(_text(it))]
        if not hits:
            continue
        entry = {
            "key": theme["key"], "name": theme["name"], "emoji": theme["emoji"],
            "note": theme["note"], "hits": hits[:per_theme], "count": len(hits),
        }
        if theme["key"] == "energia":
            entry["chokepoint"] = next(
                (cp for cp in (_chokepoint_of(_text(h)) for h in hits) if cp), None
            )
        out.append(entry)
    return out


def _theme_by_key(key: str) -> dict | None:
    return next((t for t in THEMES if t["key"] == key), None)


def _direction(text: str, theme: dict) -> str | None:
    if theme["_win_re"].search(text):
        return "beneficiado"
    if theme["_lose_re"].search(text):
        return "presionado"
    return None


def exposure(positions: list[dict], theme_key: str) -> dict[str, list[dict]]:
    """Split held positions into likely winners/losers under a given shock theme.
    Deduped by ticker (a name held across two brokers appears once)."""
    theme = _theme_by_key(theme_key)
    out: dict[str, list[dict]] = {"beneficiado": [], "presionado": []}
    if not theme:
        return out
    seen: set[str] = set()
    for pos in positions or []:
        tk = (pos.get("ticker") or "").upper()
        if not tk or tk in seen:
            continue
        text = f"{pos.get('name', '') or ''} {tk}"
        d = _direction(text, theme)
        if d:
            seen.add(tk)
            out[d].append({"ticker": tk, "name": pos.get("name") or tk})
    return out


def classify_opportunity(op: dict, theme_key: str) -> str | None:
    """Is this opportunity a likely winner/loser under the shock? (None = neutral)."""
    theme = _theme_by_key(theme_key)
    if not theme:
        return None
    text = f"{op.get('name', '') or ''} {op.get('ticker_or_isin', '') or ''} {op.get('kind', '') or ''}"
    return _direction(text, theme)
