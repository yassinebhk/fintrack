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

    async def _analyze_ticker(
        self, ticker: str, name: str, desc: str, sem: asyncio.Semaphore | None = None,
        fetch_price: bool = True,
    ) -> dict | None:
        """Generic per-instrument analysis: returns, 52w range, technical signals
        and quant factors. Used both for the fixed themes and the wide universe.

        For the wide universe we set fetch_price=False: the daily history already
        gives us everything we need, and skipping the live-price call avoids a second
        Yahoo round-trip per ticker (which, when rate-limited, falls back to slow
        yfinance scraping and makes a 100+ ticker scan crawl on small instances)."""
        async def _work() -> dict | None:
            try:
                hist = await self.yahoo.get_history(ticker, period="1y")
            except Exception as exc:
                logger.debug("{} fetch failed: {}", ticker, exc)
                return None
            if not hist or len(hist) < 30:
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

            hi, lo = max(closes), min(closes)
            range_pos = (last - lo) / (hi - lo) * 100 if hi > lo else 50.0

            # Day change: from a live price if requested, else from the last two closes.
            day_change_pct = 0.0
            if fetch_price:
                try:
                    price = await self.yahoo.get_price(ticker)
                    if price:
                        day_change_pct = price.get("change_percent", 0)
                except Exception:
                    pass
            elif len(closes) >= 2 and closes[-2]:
                day_change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100

            # Technical signals via `ta` + quant factors via empyrical (objective)
            from app.services.discovery.technical import compute_signals
            from app.services.discovery.quant_score import compute_factors
            signals = compute_signals(closes)
            factors = compute_factors(closes)

            return {
                "theme": name,
                "ticker": ticker,
                "desc": desc,
                "ret_1m": round(ret(21), 2) if ret(21) is not None else None,
                "ret_3m": round(ret(63), 2) if ret(63) is not None else None,
                "ret_6m": round(ret(126), 2) if ret(126) is not None else None,
                "ret_1y": round(ret(250), 2) if ret(250) is not None else None,
                "range_pos_52w": round(range_pos, 1),  # 0 = mínimo anual, 100 = máximo anual
                "day_change_pct": round(day_change_pct, 2),
                "signals": signals,
                "factors": factors,
            }

        if sem is not None:
            async with sem:
                return await _work()
        return await _work()

    async def _theme_momentum(self, name: str, meta: dict) -> dict | None:
        return await self._analyze_ticker(meta["ticker"], name, meta["desc"])

    # Major cryptos for the 'what's growing' trend analysis (Yahoo -USD series).
    CRYPTO_BASKET = {
        "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
        "BNB-USD": "BNB", "XRP-USD": "XRP", "ADA-USD": "Cardano",
        "AVAX-USD": "Avalanche", "DOGE-USD": "Dogecoin",
    }

    async def scan_crypto_basket(self) -> list[dict]:
        """Score a basket of major cryptos (for trend/winners analysis, not as ETF picks)."""
        sem = asyncio.Semaphore(3)  # cap peak memory (512MB free tier)
        results = await asyncio.gather(
            *(self._analyze_ticker(tk, name, "cripto", sem, fetch_price=False)
              for tk, name in self.CRYPTO_BASKET.items())
        )
        items = [r for r in results if r]
        for it in items:
            it["category"] = "cripto"
            it["region"] = "Cripto"
        from app.services.discovery.quant_score import score_universe
        if len(items) >= 2:
            score_universe(items)
        logger.info("crypto basket scan: {} of {} priced", len(items), len(self.CRYPTO_BASKET))
        return items

    async def scan_universe(self, exclude_tickers: set[str] | None = None) -> list[dict]:
        """Scan the wide curated universe + Yahoo screeners, score everything with the
        quant engine, and return the ranking. This is what surfaces instruments the
        user doesn't know — chosen by statistics, not by the LLM."""
        from app.services.discovery.universe import universe_meta

        exclude = {t.upper() for t in (exclude_tickers or set())}
        candidates = universe_meta()
        # Merge in dynamic Yahoo screener candidates (genuinely fresh names)
        for tk, info in (await self._screener_candidates()).items():
            candidates.setdefault(tk, info)

        sem = asyncio.Semaphore(3)  # low concurrency to cap peak memory on 512MB free tier (also throttles Yahoo)
        tasks = [
            self._analyze_ticker(tk, info["name"], info.get("cat", "descubierto"), sem, fetch_price=False)
            for tk, info in candidates.items()
            if tk.upper() not in exclude
        ]
        results = await asyncio.gather(*tasks)
        items = [r for r in results if r]

        # attach category/region metadata back onto each scored item
        for it in items:
            meta = candidates.get(it["ticker"], {})
            it["category"] = meta.get("cat", "")
            it["region"] = meta.get("region", "")

        from app.services.discovery.quant_score import score_universe
        score_universe(items)
        logger.info(
            "universe scan: {} of {} instruments scored (quant)", len(items), len(candidates)
        )
        return items

    async def _screener_candidates(self) -> dict[str, dict]:
        """Pull dynamic candidates from Yahoo's predefined screeners (best-effort).

        These rotate daily, so they surface names no static list contains. If the
        installed yfinance lacks screener support we just skip them silently."""
        # Quality-oriented screens only: surface solid undervalued/growth names, NOT
        # day-trade pump candidates. (day_gainers / aggressive_small_caps removed on
        # purpose — they fed speculative micro-caps into the ranking.)
        screens = {
            "undervalued_large_caps": "infravalorada (large cap)",
            "undervalued_growth_stocks": "crecimiento a buen precio (GARP)",
            "growth_technology_stocks": "tecnológica en crecimiento",
        }

        def _run() -> dict[str, dict]:
            import yfinance as yf
            found: dict[str, dict] = {}
            screen_fn = getattr(yf, "screen", None)
            if screen_fn is None:
                return found
            for key, label in screens.items():
                try:
                    res = screen_fn(key, count=10)
                    quotes = (res or {}).get("quotes", []) if isinstance(res, dict) else []
                    for q in quotes:
                        sym = q.get("symbol")
                        if not sym:
                            continue
                        found[sym] = {
                            "name": q.get("shortName") or q.get("longName") or sym,
                            "cat": f"screener · {label}",
                            "region": "EEUU",
                        }
                except Exception as exc:
                    logger.debug("screener {} failed: {}", key, exc)
            return found

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _run)
        except Exception as exc:
            logger.debug("screeners unavailable: {}", exc)
            return {}

    async def scan_themes(self) -> list[dict]:
        """Momentum snapshot of all reference themes, sorted by 3-month return."""
        results = await asyncio.gather(
            *(self._theme_momentum(name, meta) for name, meta in THEMES.items())
        )
        themes = [r for r in results if r]
        # Objective quant scoring (momentum_score / value_score) via z-scoring + empyrical
        from app.services.discovery.quant_score import score_universe
        score_universe(themes)
        logger.info("market scanner: {} themes with data (quant-scored)", len(themes))
        return themes

    def render_for_prompt(self, themes: list[dict]) -> str:
        """Render themes split into HOT (momentum/highs) vs COLD (beaten-down/possible entry)."""
        from app.services.discovery.technical import signals_label

        def line(t: dict, score_key: str) -> str:
            tech = signals_label(t.get("signals"))
            f = t.get("factors") or {}
            score = t.get(score_key)
            score_str = f"{score:+.2f}" if score is not None else "—"
            cat = t.get("category") or t.get("desc") or ""
            region = t.get("region")
            tag = f" · {cat}" + (f"/{region}" if region else "")
            base = f"- [{score_str}] {t['theme']} ({t['ticker']})"
            if not all(t.get(k) is not None for k in ("ret_1m", "ret_3m", "ret_1y")):
                return f"{base}: datos parciales{tag}"
            sharpe = f.get("sharpe")
            sharpe_str = f" · Sharpe {sharpe:+.2f}" if sharpe is not None else ""
            return (
                f"{base}: 1m {t['ret_1m']:+.1f}% · 3m {t['ret_3m']:+.1f}% · 1y {t['ret_1y']:+.1f}% · "
                f"rango52s {t['range_pos_52w']:.0f}%{sharpe_str} · [técnico: {tech}]{tag}"
            )

        scored = [t for t in themes if t.get("factors")]
        # Objective ranking from the quant engine (empyrical + ta + z-scoring), NOT LLM opinion.
        by_momentum = sorted(scored, key=lambda x: x.get("momentum_score", 0), reverse=True)
        by_value = sorted(scored, key=lambda x: x.get("value_score", 0), reverse=True)

        regime = next((t.get("market_regime") for t in scored if t.get("market_regime")), "neutral")
        breadth = next((t.get("market_breadth") for t in scored if t.get("market_breadth") is not None), None)
        regime_line = (
            f"RÉGIMEN DE MERCADO (por amplitud: % de activos sobre su tendencia de 200 sesiones): "
            f"{regime.upper()}" + (f" ({breadth:.0%} en tendencia alcista)." if breadth is not None else ".")
        )

        out = [
            "RANKING CUANTITATIVO OBJETIVO — ENSEMBLE de criterios (momentum multi-periodo, momentum "
            "absoluto/régimen, Sharpe/Sortino, técnico RSI/MACD, volatilidad EWMA, reversión a la media), "
            "combinados por z-score transversal. El número entre [ ] es la puntuación agregada, NO una opinión.",
            regime_line,
            "(En régimen alcista pesa más el momentum; en bajista, el valor/defensivo.)",
            "",
            "🔥 TOP MOMENTUM (mejor tendencia + retorno ajustado a riesgo — ordenado por momentum_score):",
        ]
        out += [line(t, "momentum_score") for t in by_momentum[:6]] or ["  (sin datos)"]
        out.append("")
        out.append(
            "🧊 TOP VALOR/CONTRARIAN (castigados/sobrevendidos pero con calidad — ordenado por value_score):"
        )
        out += [line(t, "value_score") for t in by_value[:6]] or ["  (sin datos)"]
        out.append("")
        out.append(
            "Instrucción: elige tus oportunidades SOLO de entre los temas mejor rankeados arriba. "
            "Tu trabajo es EXPLICAR los que encabezan el ranking, no reordenarlos a tu criterio."
        )
        return "\n".join(out)
