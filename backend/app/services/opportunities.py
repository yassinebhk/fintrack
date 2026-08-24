"""Opportunity discovery service — runs the market scanner + analyst agent."""

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.agents.analyst_agent import AnalystAgent
from app.agents.base import AgentContext
from app.services.discovery import MarketScanner
from app.services.market import ECBClient, FREDClient
from app.services.news import NewsService
from app.services.portfolio import PortfolioService


_DB_KEY = "opportunities"


class OpportunityService:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self._cache: dict | None = None
        self._cache_at: datetime | None = None
        # 20h so the 07:30 pre-warm keeps the cache fresh all day (an evening view
        # never falls back to a cold scan); the next morning's job refreshes it.
        self._ttl = timedelta(hours=20)
        self._lock = asyncio.Lock()
        self._generating: asyncio.Task | None = None  # background scan in flight
        self._finalizing: asyncio.Task | None = None   # background finalize from GH scan

    def _fresh(self) -> bool:
        return (
            self._cache is not None
            and self._cache_at is not None
            and datetime.now(timezone.utc) - self._cache_at < self._ttl
        )

    async def _load_from_db(self) -> dict | None:
        """Load the last payload persisted to the DB (survives redeploys, unlike the
        in-memory cache). Populates the memory cache if the stored row is still fresh."""
        try:
            from sqlalchemy import select

            from app.db import session_scope
            from app.models import JsonCache

            async with session_scope() as s:
                row = (await s.execute(select(JsonCache).where(JsonCache.key == _DB_KEY))).scalar_one_or_none()
            if not row or not row.payload:
                return None
            updated = row.updated_at
            if updated and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated and datetime.now(timezone.utc) - updated < self._ttl:
                self._cache = row.payload
                self._cache_at = updated
                return row.payload
        except Exception as exc:
            logger.warning("could not load opportunities from DB: {}", exc)
        return None

    async def _load_any_from_db(self) -> dict | None:
        """Load the last persisted payload ignoring TTL — used to serve SOMETHING
        (clearly marked as stale) instead of a perpetual 'generating' on the free
        tier, where a fresh scan may not complete reliably."""
        try:
            from sqlalchemy import select

            from app.db import session_scope
            from app.models import JsonCache

            async with session_scope() as s:
                row = (await s.execute(select(JsonCache).where(JsonCache.key == _DB_KEY))).scalar_one_or_none()
            if row and row.payload:
                updated = row.updated_at
                if updated and updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                return {"payload": row.payload, "updated_at": updated.isoformat() if updated else None}
        except Exception as exc:
            logger.warning("could not load stale opportunities from DB: {}", exc)
        return None

    async def _persist(self, payload: dict) -> None:
        try:
            from app.db import session_scope, upsert_insert
            from app.models import JsonCache

            stmt = upsert_insert()(JsonCache).values(
                key=_DB_KEY, payload=payload, updated_at=datetime.now(timezone.utc)
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={"payload": payload, "updated_at": datetime.now(timezone.utc)},
            )
            async with session_scope() as s:
                await s.execute(stmt)
        except Exception as exc:
            logger.warning("could not persist opportunities to DB: {}", exc)

    async def generate(self, *, force: bool = False) -> dict:
        """Return opportunities, generating if needed. Callers here (scheduler, bot)
        can afford to wait for the full scan."""
        if not force:
            if self._fresh():
                return self._cache
            cached = await self._load_from_db()
            if cached:
                return cached

        # Only one scan at a time: concurrent callers (manual click, daily job, bot)
        # wait for the in-flight result instead of each kicking off a heavy 100+
        # ticker scan and thrashing the instance.
        async with self._lock:
            if self._fresh() and not force:
                return self._cache
            return await self._generate_locked()

    async def peek_or_start(self, *, force: bool = False) -> dict:
        """Read-only, non-blocking entry point for the HTTP endpoint. Serves the
        cached payload (fresh or stale) and NEVER starts the heavy 130-instrument
        scan on Render — that OOMs the free tier. Fresh data is produced off-box by
        the GitHub-Actions scan worker → /ingest-scan → background finalize. So the
        web just reads; refreshes come from the daily GH scan (or a manual dispatch)."""
        if self._fresh():
            return {**self._cache, "status": "ready"}
        cached = await self._load_from_db()
        if cached:
            return {**cached, "status": "ready"}
        # No fresh cache → serve the last known payload (even if stale) so the UI is
        # never empty. A fresh one arrives via the GH scan worker, not from here.
        stale = await self._load_any_from_db()
        if stale and stale.get("payload"):
            return {**stale["payload"], "status": "stale",
                    "stale_since": stale.get("updated_at"),
                    "message": "Mostrando el último análisis; el escaneo diario lo actualiza."}
        return {"status": "generating",
                "message": "Aún no hay análisis. El escaneo diario lo generará en breve."}

    async def _background_generate(self) -> None:
        try:
            await self.generate(force=True)
            logger.info("background opportunities generation finished")
        except Exception as exc:
            logger.error("background opportunities generation failed: {}", exc)

    async def _run_scan(self) -> tuple[list[dict], list[dict]]:
        """The HEAVY part: scan + score the wide universe + crypto basket. This is
        what OOMs the 512MB free tier, so it can also be run on a GitHub-Actions
        runner (7GB) and the result fed to finalize_from_scan() instead."""
        themes, crypto = await asyncio.gather(
            self.scanner.scan_universe(),
            self.scanner.scan_crypto_basket(),
        )
        return themes, crypto

    async def finalize_from_scan(self, themes: list[dict], crypto: list[dict]) -> dict:
        """The LIGHT part: given pre-scored themes + crypto (computed here or by the
        GH-Actions worker), run trends + macro + news + the LLM analyst + enrichment,
        persist and snapshot. Cheap enough for the free tier."""
        async with self._lock:
            return await self._finalize(themes, crypto)

    def start_finalize_from_scan(self, themes: list[dict], crypto: list[dict], deliver: bool = False) -> None:
        """Fire-and-forget: accept a scan and finalize in the BACKGROUND so the HTTP
        request returns immediately (the LLM + enrichment can take >100s, past
        Render's gateway timeout → 502). The frontend polls for the fresh result.
        If deliver=True (the daily GH scan), push the result to Telegram when done."""
        async def _run():
            try:
                await self.finalize_from_scan(themes, crypto)
                logger.info("ingest-scan: background finalize done")
                if deliver:
                    from app.services.telegram_bot import TelegramBotHandler
                    await TelegramBotHandler()._send_opportunities()
                    logger.info("ingest-scan: opportunities delivered to Telegram")
            except Exception as exc:
                logger.error("ingest-scan: background finalize/deliver failed: {}", exc)
        # Dedicated slot — not shared with anything else.
        if self._finalizing is None or self._finalizing.done():
            self._finalizing = asyncio.create_task(_run())

    async def _generate_locked(self) -> dict:
        themes, crypto = await self._run_scan()
        return await self._finalize(themes, crypto)

    async def _finalize(self, themes: list[dict], crypto: list[dict]) -> dict:
        portfolio = await self.portfolio_service.calculate_portfolio()

        # Exclude what the user already holds so discoveries are genuinely new.
        held = set()
        for p in (portfolio.get("positions") or []):
            if p.get("ticker"):
                held.add(str(p["ticker"]).upper())
        # Filter held out of the scored themes (scan no longer excludes them itself,
        # so the same scan result can be reused regardless of portfolio changes).
        themes = [t for t in themes if (t.get("ticker") or "").upper() not in held]

        themes_str = self.scanner.render_for_prompt(themes)

        # Trend / winners layer (runs AFTER the ensemble): top growers + shared patterns.
        from app.services.discovery.trends import analyze_trends, winner_affinity
        trends = analyze_trends(themes, crypto)
        profile = trends.get("profile") or {}
        for t in themes:
            t["winner_affinity"] = winner_affinity(t, profile)
        trends_str = self._render_trends_for_prompt(trends)

        # Macro context (best-effort)
        us_macro, eu_macro = [], []
        try:
            us_macro = await FREDClient().snapshot()
            eu_macro = await ECBClient().snapshot()
        except Exception as exc:
            logger.warning("opportunities macro fetch partial: {}", exc)

        # Recent news (already sentiment-classified by LLM) to give the analyst current context.
        # Indexed so the analyst can reference the exact headlines that back each idea.
        news_str, news_items = "", []
        try:
            news_items = (await self.news_service.get_news("all", limit=25))[:25]
            lines = ["Titulares recientes (referénciables por su índice [N], con sentimiento):"]
            for i, n in enumerate(news_items):
                lines.append(f"[{i}] ({n.get('source')}|{n.get('impact','neutral')}) {n.get('title','')[:160]}")
            news_str = "\n".join(lines)
        except Exception as exc:
            logger.warning("opportunities news fetch failed: {}", exc)

        market_regime = next((t.get("market_regime") for t in themes if t.get("market_regime")), "neutral")
        market_breadth = next((t.get("market_breadth") for t in themes if t.get("market_breadth") is not None), None)

        # Self-training feedback: the engine's own out-of-sample track record (gated —
        # see scorecard.py — so a small/short sample is never used as if it were a
        # real pattern). Feeds AnalystAgent's conviction calibration and, for gated
        # buckets only, nudges the no-LLM template fallback below.
        from app.services.scorecard import feedback_context, render_feedback_for_prompt
        feedback = await feedback_context()
        scorecard_str = render_feedback_for_prompt(feedback)

        # Try the LLM analyst; if EVERY provider is exhausted, degrade gracefully to a
        # data-driven template so the user still gets the ranked ideas + metrics.
        ctx = AgentContext(
            portfolio=portfolio,
            extras={
                "themes_str": themes_str,
                "trends_str": trends_str,
                "macro": {"us": us_macro, "eu": eu_macro},
                "news_str": news_str,
                "scorecard_str": scorecard_str,
            },
        )
        model_used = "plantilla (sin IA)"
        market_summary = ""
        analyst_error = ""
        try:
            result = await AnalystAgent().run(ctx)
            content = result.output
            opportunities = content.get("opportunities", []) or []
            market_summary = content.get("market_summary", "")
            model_used = result.model
        except Exception as exc:
            analyst_error = str(exc)[:500]
            logger.warning("analyst LLM unavailable ({}); using data-driven template", str(exc)[:200])
            opportunities = self._template_opportunities(themes, feedback)
            market_summary = self._template_market_summary(market_regime, market_breadth, trends)
            content = {"disclaimer": "Generado automáticamente desde los datos (IA no disponible ahora)."}
        # Enrich each idea with a 6-month trend chart + the headlines that back it +
        # the ensemble score breakdown of the matching instrument.
        await self._enrich_opportunities(opportunities, news_items, {t["ticker"]: t for t in themes})

        # 🫧 Froth guard: flag overheated ideas + thematic concentration + market euphoria,
        # so a momentum engine doesn't quietly push the user into a bubble top.
        froth = self._froth_guard(themes, opportunities)

        # Surface the top of each objective ranking to the UI (the universe is large).
        scored = [t for t in themes if t.get("factors")]
        top_mom = sorted(scored, key=lambda x: x.get("momentum_score", 0), reverse=True)[:12]
        top_val = sorted(scored, key=lambda x: x.get("value_score", 0), reverse=True)[:12]
        seen, top_themes = set(), []
        for t in top_mom + top_val:
            if t["ticker"] not in seen:
                seen.add(t["ticker"])
                top_themes.append(t)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": model_used,
            "themes": top_themes,
            "universe_size": len(themes),
            "market_regime": market_regime,
            "market_breadth": market_breadth,
            "trends": trends,
            "market_summary": market_summary,
            "opportunities": opportunities,
            "froth": froth,
            "scorecard_feedback": feedback,
            "analyst_error": analyst_error,  # diagnostic: why the LLM analyst fell back
            "disclaimer": content.get("disclaimer", ""),
        }
        self._cache = payload
        self._cache_at = datetime.now(timezone.utc)
        await self._persist(payload)  # survive redeploys

        # Snapshot the recommendations for out-of-sample tracking (the scorecard).
        try:
            from app.services.scorecard import snapshot_recommendations
            await snapshot_recommendations(payload)
        except Exception as exc:
            logger.warning("scorecard snapshot failed: {}", exc)
        return payload

    def _froth_guard(self, themes: list[dict], opportunities: list[dict]) -> dict:
        """Anti-bubble guard. Detects (1) market euphoria (% of the universe
        overbought), (2) per-idea overheating (RSI extreme + far above its 200d
        trend = parabolic), and (3) thematic concentration of the recommendations.
        Pure data — flags risk, never hides ideas."""
        scored = [t for t in themes if t.get("factors")]
        # --- 1) Market euphoria thermometer ---
        rsis = [(t.get("signals") or {}).get("rsi") for t in scored]
        rsis = [r for r in rsis if r is not None]
        overbought_pct = round(sum(1 for r in rsis if r >= 70) / len(rsis) * 100, 1) if rsis else 0.0
        if overbought_pct >= 45:
            euphoria = "alta"
        elif overbought_pct >= 25:
            euphoria = "media"
        else:
            euphoria = "baja"

        # --- 2) Per-idea overheating flags ---
        by_ticker = {t.get("ticker"): t for t in scored}
        extended_ideas = []
        for op in opportunities:
            tk = (op.get("ticker_or_isin") or "").upper()
            t = by_ticker.get(tk)
            if not t:
                continue
            f = t.get("factors") or {}
            rsi = (t.get("signals") or {}).get("rsi")
            dist = f.get("dist_sma200")  # fraction above its 200d trend
            extended = (rsi is not None and rsi >= 78) and (dist is not None and dist >= 0.40)
            op["extended"] = bool(extended)
            if extended:
                op["extended_note"] = (
                    f"🫧 Extendido: RSI {rsi:.0f} y {dist*100:.0f}% por encima de su tendencia de 200 sesiones "
                    "(parabólico). Alto riesgo de reversión brusca — no persigas el pico."
                )
                extended_ideas.append(tk)

        # --- 3) Thematic concentration of the recommendations ---
        from collections import Counter
        cats = Counter((op.get("kind") or "") + "|" + (by_ticker.get((op.get("ticker_or_isin") or "").upper(), {}).get("category") or "")
                       for op in opportunities)
        # Simpler: count by the matched instrument's category.
        cat_counts = Counter()
        for op in opportunities:
            t = by_ticker.get((op.get("ticker_or_isin") or "").upper())
            if t and t.get("category"):
                cat_counts[t["category"]] += 1
        concentration_warning = ""
        if opportunities and cat_counts:
            top_cat, top_n = cat_counts.most_common(1)[0]
            if top_n >= max(3, len(opportunities) * 0.6):
                concentration_warning = (
                    f"⚠️ {top_n} de {len(opportunities)} ideas son de '{top_cat}'. Si ese tema corrige, "
                    "te afectaría en bloque — valora diversificar entre temas."
                )

        return {
            "market_overbought_pct": overbought_pct,
            "euphoria_level": euphoria,
            "extended_ideas": extended_ideas,
            "concentration_warning": concentration_warning,
            "note": (
                "El froth guard avisa de sobrecalentamiento; no oculta ideas. En euforia alta, "
                "extrema la cautela con el momentum y revisa tu exposición."
            ),
        }

    def _template_opportunities(self, themes: list[dict], feedback: dict | None = None) -> list[dict]:
        """Build opportunities straight from the quant ranking when no LLM is
        available — same shape as the LLM output, text generated from the data.
        Keeps the core product alive (data, ranking, metrics) without any AI."""
        scored = [t for t in themes if t.get("factors")]
        if not scored:
            return []
        top_mom = sorted(scored, key=lambda x: x.get("momentum_score", 0), reverse=True)[:3]
        top_val = sorted(scored, key=lambda x: x.get("value_score", 0), reverse=True)[:3]

        by_approach = (feedback or {}).get("by_approach") or {}

        def conviction(score: float, approach: str) -> str:
            base = "alta" if score >= 1.0 else "media" if score >= 0.3 else "baja"
            # Deterministic, non-LLM nudge — only acts once this approach's real
            # track record clears the anti-noise gate (scorecard.MIN_N_FEEDBACK /
            # MIN_SPAN_DAYS_FEEDBACK). Until then this is a documented no-op.
            stats = by_approach.get(approach)
            if stats and stats.get("gated") and stats.get("median", 0) <= 0:
                order = ["baja", "media", "alta"]
                base = order[max(0, order.index(base) - 1)]
            return base

        def signals_txt(t: dict) -> str:
            s = t.get("signals") or {}
            bits = []
            if s.get("rsi") is not None:
                bits.append(f"RSI {s['rsi']:.0f} ({s.get('rsi_signal','')})")
            if s.get("trend"):
                bits.append(f"tendencia {s['trend']}")
            if s.get("macd_signal"):
                bits.append(f"MACD {s['macd_signal']}")
            return ", ".join(bits)

        def make(t: dict, approach: str, score: float) -> dict:
            f = t.get("factors") or {}
            cat = t.get("category") or t.get("desc") or ""
            why = (
                f"El motor cuantitativo lo sitúa en lo más alto de {('MOMENTUM' if approach=='momentum' else 'VALOR')} "
                f"(score {score:+.2f}). Datos: 3m {t.get('ret_3m','?')}% · 1y {t.get('ret_1y','?')}% · "
                f"Sharpe {f.get('sharpe','?')} · rango52s {t.get('range_pos_52w','?')}%."
            )
            tech = signals_txt(t)
            if tech:
                why += f" Técnico: {tech}."
            risks = (
                "Volatilidad y posible sobrecompra (RSI alto)."
                if (t.get("signals") or {}).get("rsi", 0) and t["signals"]["rsi"] > 70
                else "Drawdown histórico y riesgo de mercado; revisa antes de entrar."
            )
            return {
                "name": t.get("theme") or t.get("ticker"),
                "kind": "etf",
                "approach": approach,
                "ticker_or_isin": t.get("ticker", ""),
                "what_it_is": f"{cat}." if cat else "Instrumento del universo escaneado.",
                "why_now": why,
                "risks": risks,
                "fit": "Revisa su encaje y correlación con lo que ya tienes en cartera.",
                "conviction": conviction(score, approach),
                "supporting_news_idx": [],
            }

        out, seen = [], set()
        for t in top_mom:
            if t["ticker"] not in seen:
                seen.add(t["ticker"])
                out.append(make(t, "momentum", t.get("momentum_score", 0)))
        for t in top_val:
            if t["ticker"] not in seen:
                seen.add(t["ticker"])
                out.append(make(t, "valor", t.get("value_score", 0)))
        return out

    def _template_market_summary(self, regime: str, breadth: float | None, trends: dict) -> str:
        pct = f" ({round(breadth*100)}% de activos sobre su tendencia de 200 sesiones)" if breadth is not None else ""
        patterns = (trends or {}).get("patterns") or []
        extra = (" " + patterns[0]) if patterns else ""
        return (
            f"Régimen de mercado: {regime}{pct}. Ranking generado por el motor cuantitativo "
            f"(IA de redacción no disponible ahora mismo).{extra}"
        )

    def _render_trends_for_prompt(self, trends: dict) -> str:
        """Compact 'what's growing + shared patterns' block for the analyst prompt."""
        lines = ["TENDENCIAS DEL MOMENTO — qué más ha crecido (últimos meses) y patrones comunes:"]
        gr = trends.get("top_growers_etf") or []
        if gr:
            lines.append("Top ETFs/fondos por crecimiento:")
            for g in gr[:6]:
                r3 = g.get("ret_3m")
                lines.append(f"  · {g['name']} ({g['ticker']}): 3m {r3:+.0f}%" if r3 is not None
                             else f"  · {g['name']} ({g['ticker']})")
        cr = trends.get("top_growers_crypto") or []
        if cr:
            lines.append("Top cripto por crecimiento:")
            for g in cr[:5]:
                r3 = g.get("ret_3m")
                lines.append(f"  · {g['name']} ({g['ticker']}): 3m {r3:+.0f}%" if r3 is not None
                             else f"  · {g['name']} ({g['ticker']})")
        if trends.get("patterns"):
            lines.append("Patrones comunes detectados:")
            lines += [f"  - {p}" for p in trends["patterns"]]
        lines.append(
            "Úsalo como CONTEXTO: si una idea encaja con el patrón ganador, dilo; si el patrón está "
            "muy extendido (RSI alto), advierte del riesgo de comprar caro. No persigas máximos a ciegas."
        )
        return "\n".join(lines)

    async def _enrich_opportunities(
        self, opportunities: list[dict], news_items: list[dict], by_ticker: dict[str, dict] | None = None
    ) -> None:
        """Attach a 6-month trend chart_url, supporting news (with links) and the
        ensemble score breakdown of the matching instrument to each idea."""
        from app.services.charts import line_chart

        by_ticker = by_ticker or {}

        def attach_scores(opp: dict) -> None:
            tk = (opp.get("ticker_or_isin") or "").strip().upper()
            t = by_ticker.get(tk)
            if not t:
                return
            opp["scores"] = {
                "momentum_score": t.get("momentum_score"),
                "value_score": t.get("value_score"),
            }
            opp["winner_affinity"] = t.get("winner_affinity")
            # Show the breakdown for the thesis the analyst chose (momentum vs value).
            which = "value" if opp.get("approach") in ("valor", "contrarian") else "momentum"
            bd = (t.get("breakdown") or {}).get(which) or {}
            # sorted by absolute contribution, biggest drivers first
            opp["score_breakdown"] = dict(sorted(bd.items(), key=lambda kv: abs(kv[1]), reverse=True))

        def attach_news(opp: dict) -> None:
            refs = []
            for idx in (opp.get("supporting_news_idx") or [])[:2]:
                if isinstance(idx, int) and 0 <= idx < len(news_items):
                    n = news_items[idx]
                    refs.append({"title": n.get("title", ""), "url": n.get("url", ""),
                                 "source": n.get("source", ""), "impact": n.get("impact", "neutral")})
            opp["news"] = refs

        async def attach_chart(opp: dict) -> None:
            ticker = (opp.get("ticker_or_isin") or "").strip().upper()
            if not ticker:
                return
            try:
                hist = await self.scanner.yahoo.get_history(ticker, period="6mo")
                closes = [h["close"] for h in (hist or []) if h.get("close")]
                labels = [h["date"] for h in (hist or []) if h.get("close")]
                if len(closes) >= 20:
                    up = closes[-1] >= closes[0]
                    color = "#10b981" if up else "#ef4444"
                    title = f"{opp.get('name', ticker)} · 6 meses"
                    opp["chart_url"] = line_chart(title[:60], labels, closes, color=color)
            except Exception as exc:
                logger.debug("chart for {} failed: {}", ticker, exc)

        for opp in opportunities:
            attach_news(opp)
            attach_scores(opp)
        await asyncio.gather(*(attach_chart(o) for o in opportunities))


def render_opportunities_telegram(payload: dict) -> str:
    from app.services.notifications.telegram import html_escape as esc

    parts = ["💡 <b>Oportunidades del día</b>", ""]
    if payload.get("market_summary"):
        parts.append(f"<i>{esc(payload['market_summary'])}</i>")
        parts.append("")

    conv_emoji = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
    appr_emoji = {"momentum": "🔥", "valor": "🧊", "contrarian": "🧊"}
    for op in payload.get("opportunities", []):
        emoji = conv_emoji.get(op.get("conviction", "media"), "🟡")
        ap = op.get("approach", "")
        ap_tag = f" {appr_emoji.get(ap,'')}{esc(ap)}" if ap else ""
        name = esc(op.get("name", ""))
        kind = esc(op.get("kind", ""))
        tk = op.get("ticker_or_isin")
        header = f"{emoji} <b>{name}</b> ({kind}{', ' + esc(tk) if tk else ''}){ap_tag}"
        parts.append(header)
        parts.append(f"<b>Qué es:</b> {esc(op.get('what_it_is',''))}")
        parts.append(f"<b>Por qué ahora:</b> {esc(op.get('why_now',''))}")
        parts.append(f"<b>Riesgos:</b> {esc(op.get('risks',''))}")
        parts.append(f"<b>Encaje:</b> {esc(op.get('fit',''))}")
        parts.append("")

    if payload.get("disclaimer"):
        parts.append(f"<i>{esc(payload['disclaimer'])}</i>")
    parts.append('\n🔗 <a href="https://fintrack-front.onrender.com">Ver más en FinTrack</a>')
    return "\n".join(parts).strip()


def render_opportunity_caption(op: dict) -> str:
    """Compact HTML caption for an opportunity photo (Telegram caps captions at 1024)."""
    from app.services.notifications.telegram import html_escape as esc

    conv_emoji = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
    appr_emoji = {"momentum": "🔥", "valor": "🧊", "contrarian": "🧊"}
    emoji = conv_emoji.get(op.get("conviction", "media"), "🟡")
    ap = op.get("approach", "")
    ap_tag = f" {appr_emoji.get(ap,'')}{esc(ap)}" if ap else ""
    tk = op.get("ticker_or_isin")
    lines = [
        f"{emoji} <b>{esc(op.get('name',''))}</b>"
        f"{' (' + esc(tk) + ')' if tk else ''}{ap_tag}",
        f"<b>Qué es:</b> {esc(op.get('what_it_is','')[:280])}",
        f"<b>Por qué ahora:</b> {esc(op.get('why_now','')[:320])}",
        f"<b>Riesgos:</b> {esc(op.get('risks','')[:200])}",
    ]
    bd = op.get("score_breakdown") or {}
    if bd:
        labels = {
            "momentum": "Momentum", "regimen": "Régimen", "riesgo": "Sharpe",
            "tecnico": "Técnico", "volatilidad": "Volatilidad", "infravaloracion": "Infravalorado",
            "reversion": "Reversión", "sobreventa": "Sobreventa", "calidad": "Calidad",
        }
        top = list(bd.items())[:3]  # already sorted by |contribution|
        chips = " · ".join(f"{labels.get(k,k)} {'+' if v>=0 else ''}{v:.2f}" for k, v in top)
        lines.append(f"<b>🧮 Criterios:</b> <i>{esc(chips)}</i>")
    if tk:
        from urllib.parse import quote
        lines.append(f'🔗 <a href="https://finance.yahoo.com/quote/{quote(str(tk))}">Ver ficha (precio e info)</a>')
    news = op.get("news") or []
    if news:
        lines.append("<b>📰 Noticias que lo respaldan:</b>")
        for n in news[:2]:
            title = esc((n.get("title", "") or "")[:110])
            url = n.get("url", "")
            src = esc(n.get("source", ""))
            lines.append(f"• <a href=\"{url}\">{title}</a> <i>({src})</i>" if url else f"• {title} <i>({src})</i>")
    return "\n".join(lines)[:1024]


# Single shared instance so the in-memory cache is the same one the API endpoint,
# the Telegram bot and the daily pre-warm job all read from / write to.
_shared_service: OpportunityService | None = None


def get_opportunity_service() -> OpportunityService:
    global _shared_service
    if _shared_service is None:
        _shared_service = OpportunityService()
    return _shared_service
