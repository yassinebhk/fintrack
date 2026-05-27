"""Sector / theme momentum scanner using reference ETFs (Yahoo Finance).

Gives the AI analyst real data about *what is actually moving* in the market,
so opportunity suggestions are grounded in facts, not just the LLM's guesses.
"""

import asyncio
from datetime import datetime

from loguru import logger

from app.services.market.yahoo_finance import YahooFinanceService


# Reference ETFs per theme/sector. Each maps to a Yahoo ticker with liquid history.
# Chosen to be UCITS/EUR where possible, falling back to large US ETFs.
THEMES: dict[str, dict] = {
    "Energía limpia": {"ticker": "ICLN", "desc": "Energía renovable y limpia global"},
    "Tecnología / IA": {"ticker": "QQQ", "desc": "Tecnología y Nasdaq-100 (incluye gigantes de IA)"},
    "Semiconductores": {"ticker": "SOXX", "desc": "Fabricantes de chips (núcleo de la IA)"},
    "Value global": {"ticker": "IWVL.L", "desc": "Acciones value (infravaloradas) globales"},
    "Mercados emergentes": {"ticker": "EEM", "desc": "Bolsa de mercados emergentes"},
    "Oro": {"ticker": "GLD", "desc": "Oro físico — refugio e inflación"},
    "Defensa / aeroespacial": {"ticker": "ITA", "desc": "Industria de defensa y aeroespacial"},
    "Salud / biotech": {"ticker": "XLV", "desc": "Sector salud y farmacéuticas"},
    "Dividendos": {"ticker": "VYM", "desc": "Empresas de alto dividendo"},
    "Europa": {"ticker": "VGK", "desc": "Bolsa europea desarrollada"},
    "Agua": {"ticker": "PHO", "desc": "Tema agua y tratamiento"},
    "Bonos agregados": {"ticker": "AGG", "desc": "Renta fija agregada (refugio defensivo)"},
}


class MarketScanner:
    def __init__(self) -> None:
        self.yahoo = YahooFinanceService()

    async def _theme_momentum(self, name: str, meta: dict) -> dict | None:
        ticker = meta["ticker"]
        try:
            hist = await self.yahoo.get_history(ticker, period="1y")
            price = await self.yahoo.get_price(ticker)
        except Exception as exc:
            logger.debug("theme {} fetch failed: {}", name, exc)
            return None
        if not hist or len(hist) < 30 or not price:
            return None

        closes = [h["close"] for h in hist if h.get("close")]
        if len(closes) < 30:
            return None

        last = closes[-1]

        def ret(days_back: int) -> float | None:
            if len(closes) > days_back:
                base = closes[-days_back - 1]
                return (last - base) / base * 100 if base else None
            return None

        # 52-week range position
        hi = max(closes)
        lo = min(closes)
        range_pos = (last - lo) / (hi - lo) * 100 if hi > lo else 50.0

        # Technical signals via the `ta` library (objective, not LLM opinion)
        from app.services.discovery.technical import compute_signals
        signals = compute_signals(closes)

        return {
            "theme": name,
            "ticker": ticker,
            "desc": meta["desc"],
            "ret_1m": round(ret(21), 2) if ret(21) is not None else None,
            "ret_3m": round(ret(63), 2) if ret(63) is not None else None,
            "ret_6m": round(ret(126), 2) if ret(126) is not None else None,
            "ret_1y": round(ret(250), 2) if ret(250) is not None else None,
            "range_pos_52w": round(range_pos, 1),  # 0 = mínimo anual, 100 = máximo anual
            "day_change_pct": round(price.get("change_percent", 0), 2),
            "signals": signals,
        }

    async def scan_themes(self) -> list[dict]:
        """Momentum snapshot of all reference themes, sorted by 3-month return."""
        results = await asyncio.gather(
            *(self._theme_momentum(name, meta) for name, meta in THEMES.items())
        )
        themes = [r for r in results if r]
        themes.sort(key=lambda x: (x.get("ret_3m") or -999), reverse=True)
        logger.info("market scanner: {} themes with data", len(themes))
        return themes

    def render_for_prompt(self, themes: list[dict]) -> str:
        """Render themes split into HOT (momentum/highs) vs COLD (beaten-down/possible entry)."""
        from app.services.discovery.technical import signals_label

        def line(t: dict) -> str:
            if not all(t.get(k) is not None for k in ("ret_1m", "ret_3m", "ret_1y")):
                return f"- {t['theme']} ({t['ticker']}): datos parciales · {t['desc']}"
            tech = signals_label(t.get("signals"))
            return (
                f"- {t['theme']} ({t['ticker']}): "
                f"1m {t['ret_1m']:+.1f}% · 3m {t['ret_3m']:+.1f}% · 1y {t['ret_1y']:+.1f}% · "
                f"rango52s {t['range_pos_52w']:.0f}% · [técnico: {tech}] · {t['desc']}"
            )

        # Classify: hot = near 52w highs / strong; cold = near lows / corrected (contrarian candidates)
        hot, cold, mid = [], [], []
        for t in themes:
            rp = t.get("range_pos_52w")
            if rp is None:
                mid.append(t)
            elif rp >= 70:
                hot.append(t)
            elif rp <= 40:
                cold.append(t)
            else:
                mid.append(t)

        out = ["Datos reales de momentum por tema (ETFs de referencia).", ""]
        out.append("🔥 CALIENTES (cerca de máximos 52s — tesis MOMENTUM, ojo a que estén caros):")
        out += [line(t) for t in hot] or ["  (ninguno)"]
        out.append("")
        out.append("🧊 EN CORRECCIÓN / ZONA BAJA (cerca de mínimos 52s — posibles tesis VALOR/CONTRARIAN si hay catalizador):")
        out += [line(t) for t in cold] or ["  (ninguno)"]
        if mid:
            out.append("")
            out.append("➖ INTERMEDIOS:")
            out += [line(t) for t in mid]
        return "\n".join(out)
