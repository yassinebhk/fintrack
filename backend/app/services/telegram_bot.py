"""Inbound Telegram message handler — makes the bot conversational.

Two capabilities:
1. Answer questions about the portfolio (delegates to FinBot / LLM with rich context).
2. Add money to a fund via natural language or /aportar command.

Security: only the configured TELEGRAM_CHAT_ID is allowed to interact.
"""

import asyncio
import re
from datetime import date, timedelta

from loguru import logger

from app.config import get_settings
from app.db import session_scope
from app.llm import LLMMessage, get_llm_client
from app.repositories import PositionRepository, SnapshotRepository
from app.services.charts import line_chart
from app.services.notifications.telegram import TelegramNotifier, html_escape
from app.services.portfolio import PortfolioService


PAGE_URL = "https://fintrack-front.onrender.com"
PAGE_LINK = f'\n\n🔗 <a href="{PAGE_URL}">Ver más en FinTrack</a>'

# Friendly display names so we never show raw ISINs to the user
FRIENDLY_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "DOGE": "Dogecoin",
    "PEPE": "Pepe",
    "IE00BYX5NX33": "Fidelity MSCI World",
    "IE00B4ND3602": "Oro físico (iShares)",
    "LYX0F.DE": "Nasdaq-100 (Amundi)",
}


def friendly_name(ticker: str, asset_name: str | None = None) -> str:
    if ticker in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[ticker]
    if asset_name:
        return asset_name
    return ticker


HELP_TEXT = (
    "🤖 <b>FinBot</b> — tu asistente de cartera\n\n"
    "Puedes:\n"
    "• Preguntarme cualquier cosa: <i>¿cuánto he ganado esta semana?</i>, "
    "<i>resumen de mi bitcoin</i>, <i>¿cómo está diversificada mi cartera?</i>\n"
    "• Pedir gráficas: <i>gráfica de mi cartera</i>, <i>gráfico de bitcoin</i>\n"
    "• <b>Oportunidades de inversión</b>: <code>/oportunidades</code> — el analista rastrea el mercado y te trae ideas\n"
    "• Aportar dinero: <code>/aportar oro 50</code> o <i>he metido 50€ al nasdaq</i>\n"
    "• <code>/cartera</code> — resumen rápido\n"
    "• <code>/ayuda</code> — este mensaje"
    + PAGE_LINK
)

CONTRIBUTE_KEYWORDS = ("aporta", "aporté", "aporte", "mete", "metí", "meti", "añad", "anad",
                       "invierto", "invertí", "inverti", "compr", "ingreso", "ingresé")

CHART_KEYWORDS = ("gráfic", "grafic", "chart", "evolución", "evolucion", "muéstrame", "muestrame")

# Natural-language ways of asking "what should I invest in?" — route to opportunities,
# not to the contribution flow (which also matches "invierto") or the generic Q&A.
OPPORTUNITY_QUERY_PATTERNS = (
    "en que invierto", "en qué invierto", "que invierto hoy", "qué invierto hoy",
    "donde invierto", "dónde invierto", "en que invertir", "en qué invertir",
    "donde meto el dinero", "dónde meto el dinero", "donde meto la pasta", "dónde meto la pasta",
    "que compro", "qué compro",
    "que recomiend", "qué recomiend", "recomendacion", "recomendación",
    "ideas de hoy", "ideas hoy", "ideas para hoy",
    "que hago hoy", "qué hago hoy", "que hago con mi dinero", "qué hago con mi dinero",
    "donde entrar", "dónde entrar", "en que entrar", "en qué entrar",
    "que oportunidad", "qué oportunidad",
)

NEWS_QUERY_PATTERNS = (
    "noticias", "titular", "qué pasa en el mercado", "que pasa en el mercado",
    "qué hay de nuevo", "que hay de nuevo", "actualidad", "qué ha pasado hoy",
    "que ha pasado hoy",
)

BRIEFING_QUERY_PATTERNS = ("briefing", "resumen del día", "resumen del dia", "informe diario")

MARKET_QUERY_PATTERNS = (
    "cómo está el mercado", "como esta el mercado", "estado del mercado",
    "está alcista", "esta alcista", "está bajista", "esta bajista", "régimen del mercado", "regimen del mercado",
)

GREETING_PATTERNS = ("hola", "buenas", "buenos días", "buenos dias", "buenas tardes", "buenas noches", "hey", "ey")
THANKS_PATTERNS = ("gracias", "thanks", "mil gracias", "muchas gracias")

DEEP_ANALYSIS_TRIGGERS = ("/analizar", "analiza ", "análisis de ", "analisis de ", "analizame ",
                          "análisis profesional", "analisis profesional", "deep ")


class TelegramBotHandler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.notifier = TelegramNotifier()
        self.portfolio_service = PortfolioService()

    async def handle(self, chat_id: str, text: str) -> None:
        # Authorization: only the configured chat
        if str(chat_id) != str(self.settings.telegram_chat_id):
            logger.warning("telegram: ignoring message from unauthorized chat {}", chat_id)
            return

        text = (text or "").strip()
        if not text:
            return

        low = text.lower()

        if low in ("/start", "/help", "/ayuda", "ayuda"):
            await self.notifier.send_html(HELP_TEXT)
            return

        if low in ("/cartera", "cartera", "resumen"):
            await self._send_quick_summary()
            return

        if low in ("/scorecard", "scorecard", "aciertos", "rendimiento del sistema", "qué tal acierta"):
            await self._send_scorecard()
            return

        if low in ("/revision", "/revisión", "revisa mi cartera", "revisión", "revision",
                    "¿vendo o mantengo?", "vendo o mantengo", "qué hago con mis posiciones"):
            await self._send_position_review()
            return

        if low in ("/planes", "planes", "mis planes", "como van mis planes", "cómo van mis planes"):
            await self._send_plans()
            return

        if low in ("/oportunidades", "oportunidades", "ideas", "recomendaciones", "que compro", "qué compro"):
            await self._send_opportunities()
            return

        # Natural-language "what should I invest in?" → opportunities (must come
        # BEFORE the contribution intent, since "invierto" overlaps both).
        if any(p in low for p in OPPORTUNITY_QUERY_PATTERNS):
            await self._send_opportunities()
            return

        # Deep per-asset analysis (must come before news/contribution; matches "/analizar TICKER" or "analiza X")
        if any(low.startswith(t) or (' ' + t in ' ' + low) for t in DEEP_ANALYSIS_TRIGGERS):
            target = self._extract_analysis_target(text)
            if target:
                await self._send_deep_analysis(target)
            else:
                await self.notifier.send_text(
                    "¿Qué activo quieres analizar? Dime el ticker — p.ej. /analizar SOXX, /analizar MU, /analizar BTC-USD."
                )
            return

        # News / market / briefing intents (natural language)
        if any(p in low for p in NEWS_QUERY_PATTERNS):
            await self._send_news_digest()
            return
        if any(p in low for p in BRIEFING_QUERY_PATTERNS):
            await self._send_briefing()
            return
        if any(p in low for p in MARKET_QUERY_PATTERNS):
            await self._send_market_state()
            return

        # Small talk — quick friendly replies (only when the message is JUST a greeting/thanks)
        if low.rstrip("?¿!¡. ") in GREETING_PATTERNS:
            await self.notifier.send_html(
                "👋 ¡Hola! Soy <b>FinBot</b>. Prueba: <code>/cartera</code> · <code>/oportunidades</code> · "
                "o pregúntame en lenguaje natural — <i>'¿en qué invierto hoy?'</i>, <i>'¿noticias?'</i>, "
                "<i>'gráfica de bitcoin'</i>, <i>'mete 50€ al oro desde Kraken'</i>."
            )
            return
        if low.rstrip("?¿!¡. ") in THANKS_PATTERNS:
            await self.notifier.send_text("¡De nada! 😉")
            return

        # Chart intent?
        if any(k in low for k in CHART_KEYWORDS):
            await self._send_chart(text)
            return

        # Contribution intent?
        if low.startswith("/aportar") or self._looks_like_contribution(low):
            handled = await self._try_contribution(text)
            if handled:
                return
            # fall through to Q&A if we couldn't parse it

        # Otherwise treat as a question for FinBot
        await self._answer_question(text)

    async def _keep_thinking(self) -> None:
        """Keep the 'typing…' indicator alive while a long task runs (it expires ~5s)."""
        try:
            while True:
                await self.notifier.send_chat_action("typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            return

    async def _send_opportunities(self) -> None:
        """Run the market analyst and send today's opportunities."""
        await self.notifier.send_text(
            "🧠 Estoy analizando el mercado y buscando oportunidades…\n"
            "Escaneo ~130 activos + noticias y preparo las gráficas. "
            "Puede tardar 1-2 min la primera vez del día."
        )
        thinking = asyncio.create_task(self._keep_thinking())  # keep "typing…" visible
        try:
            from app.services.opportunities import (
                get_opportunity_service,
                render_opportunities_telegram,
                render_opportunity_caption,
            )

            payload = await get_opportunity_service().generate()
            thinking.cancel()  # done thinking → stop the typing indicator
            opps = payload.get("opportunities") or []
            if not opps:
                await self.notifier.send_text("No pude generar oportunidades ahora mismo (posible límite de cuota). Reintenta en un rato.")
                return

            # Market summary first, then one trend chart per idea (with the news that backs it).
            if payload.get("market_summary"):
                regime = payload.get("market_regime")
                breadth = payload.get("market_breadth")
                regime_line = ""
                if regime:
                    emoji = {"alcista": "🟢", "bajista": "🔴", "neutral": "🟡"}.get(regime, "🟡")
                    pct = f" ({round(breadth*100)}% sobre su tendencia 200d)" if breadth is not None else ""
                    regime_line = f"\n{emoji} <b>Régimen:</b> {regime}{pct}"
                # 🫧 Froth guard line (euphoria / concentration / extended ideas)
                fr = payload.get("froth") or {}
                froth_line = ""
                if fr.get("euphoria_level") and (fr["euphoria_level"] != "baja" or fr.get("concentration_warning")):
                    fe = {"alta": "🟣", "media": "🟠", "baja": "🟢"}.get(fr["euphoria_level"], "")
                    froth_line = f"\n{fe} <b>Euforia:</b> {fr['euphoria_level']} ({fr.get('market_overbought_pct',0)}% sobrecomprado)"
                    if fr.get("concentration_warning"):
                        froth_line += f"\n{fr['concentration_warning']}"
                    if fr.get("extended_ideas"):
                        froth_line += f"\n🫧 Extendidas: {', '.join(fr['extended_ideas'])}"
                await self.notifier.send_html(
                    f"💡 <b>Oportunidades del día</b>{regime_line}{froth_line}\n\n<i>{payload['market_summary']}</i>"
                )
            # 'What's growing' trend block (winners + shared patterns)
            trends = payload.get("trends") or {}
            if trends.get("top_growers_etf") or trends.get("patterns"):
                tl = ["🚀 <b>Tendencias del momento</b>"]
                etf = trends.get("top_growers_etf") or []
                if etf:
                    tl.append("<b>ETFs/fondos que más suben (3m):</b>")
                    for g in etf[:5]:
                        r3 = g.get("ret_3m")
                        tl.append(f"• {g.get('name')} ({g.get('ticker')}){f': {r3:+.0f}%' if r3 is not None else ''}")
                cr = trends.get("top_growers_crypto") or []
                if cr:
                    tl.append("<b>Cripto que más sube (3m):</b>")
                    for g in cr[:4]:
                        r3 = g.get("ret_3m")
                        tl.append(f"• {g.get('name')} ({g.get('ticker')}){f': {r3:+.0f}%' if r3 is not None else ''}")
                if trends.get("patterns"):
                    tl.append("<b>🔁 Patrones comunes:</b>")
                    tl += [f"• {p}" for p in trends["patterns"][:4]]
                await self.notifier.send_html("\n".join(tl))
            sent_any_chart = False
            for op in opps:
                caption = render_opportunity_caption(op)
                if op.get("chart_url"):
                    await self.notifier.send_chat_action("upload_photo")
                    ok = await self.notifier.send_photo(op["chart_url"], caption=caption)
                    sent_any_chart = sent_any_chart or ok
                    if not ok:  # chart failed → at least send the text
                        await self.notifier.send_html(caption)
                else:
                    await self.notifier.send_html(caption)
            # Fallback: if not a single chart went through, send the full text digest.
            if not sent_any_chart:
                await self.notifier.send_html(render_opportunities_telegram(payload))
            else:
                await self.notifier.send_html('🔗 <a href="https://fintrack-front.onrender.com">Ver todo en FinTrack</a>')
        except Exception as exc:
            logger.error("telegram opportunities failed: {}", exc)
            await self.notifier.send_text("No pude generar las oportunidades ahora mismo, intenta más tarde.")
        finally:
            thinking.cancel()  # safety: always stop the indicator

    def _extract_analysis_target(self, text: str) -> str | None:
        """Pull a ticker out of '/analizar SOXX', 'analiza el MU', etc.
        Also tries to match the user's words against tickers/names of the cached opportunities."""
        import re
        t = text.strip()
        m = re.match(r"^/analizar\s+([A-Za-z0-9\.\-]+)", t)
        if m:
            return m.group(1).upper()
        low = t.lower()
        # 1) Any uppercase-looking token in the message (TICKER style)
        for tok in re.findall(r"\b([A-Z][A-Z0-9\.\-]{1,12})\b", t):
            if tok.lower() not in ("ETF", "ISIN", "FAQ", "AI", "IA"):
                return tok.upper()
        # 2) Match against tickers/names in the cached opportunities
        try:
            from app.services.opportunities import get_opportunity_service
            cached = get_opportunity_service()._cache or {}
            themes = (cached.get("themes") or []) + (cached.get("opportunities") or [])
            for th in themes:
                tk = (th.get("ticker") or th.get("ticker_or_isin") or "")
                nm = (th.get("theme") or th.get("name") or "")
                if tk and tk.lower() in low:
                    return tk.upper()
                if nm and nm.lower() in low:
                    return tk.upper() if tk else None
        except Exception:
            pass
        return None

    async def _send_deep_analysis(self, ticker: str) -> None:
        """Run the deep per-asset analysis and stream the results via Telegram."""
        await self.notifier.send_html(
            f"🔬 Análisis profesional de <b>{html_escape(ticker)}</b>… (~10-30s)"
        )
        thinking = asyncio.create_task(self._keep_thinking())
        try:
            from app.services.asset_analysis import analyze_asset
            d = await analyze_asset(ticker)
            thinking.cancel()

            m = d.get("metrics", {}) or {}
            sc = d.get("scores", {}) or {}
            bench = (d.get("benchmark") or {}).get("name", "benchmark")

            def s(n, d_=2):
                return f"{n:+.{d_}f}" if isinstance(n, (int, float)) else "—"

            def _nv(x, fmt="{:+.2f}"):  # None-safe formatter
                return "n/d" if x is None else fmt.format(x)
            psr = m.get("psr_pct")
            jb_p = m.get("jarque_bera_p")
            ir = m.get("information_ratio")
            tr = m.get("treynor_pct")
            header = (
                f"🔬 <b>{html_escape(d.get('name', ticker))}</b> ({ticker})\n"
                f"<i>{html_escape((d.get('category') or '').strip())} · {html_escape((d.get('region') or '').strip())} · vs {bench} · Rf {m.get('rf_annual_pct','—')}%</i>\n\n"
                f"<b>Rentabilidad / Riesgo</b>\n"
                f"• CAGR {_nv(m.get('cagr_pct'))}% · Vol {m.get('volatility_pct','—')}%\n"
                f"• Sharpe {_nv(m.get('sharpe'))} · Sortino {_nv(m.get('sortino'))} · Calmar {m.get('calmar','—')}\n"
                f"• Máx. DD {_nv(m.get('max_drawdown_pct'))}% · duración {m.get('max_drawdown_days','—')}d (media {m.get('avg_drawdown_days','—')}d)\n\n"
                f"<b>Cola y distribución</b>\n"
                f"• VaR 95/99 {m.get('var_95_pct','—')}% / {m.get('var_99_pct','—')}%\n"
                f"• CVaR 95/99 {m.get('cvar_95_pct','—')}% / {m.get('cvar_99_pct','—')}%\n"
                f"• Skew {_nv(m.get('skewness'))} · Curtosis exc. {_nv(m.get('excess_kurtosis'))}\n"
                f"• Jarque-Bera p={_nv(jb_p,'{:.4f}')} ({'no-normal' if (jb_p is not None and jb_p<0.05) else '≈normal'})\n"
                f"• PSR (prob. Sharpe&gt;0) {_nv(psr,'{:.1f}')}%\n\n"
                f"<b>Frente al benchmark</b>\n"
                f"• Beta {m.get('beta','—')} · α anual {_nv(m.get('alpha_annual_pct'))}%"
                f" (t={_nv(m.get('alpha_t_stat'),'{:+.2f}')}, p={_nv(m.get('alpha_p_value'),'{:.4f}')})\n"
                f"• Corr {m.get('correlation','—')} · R² {m.get('r_squared_pct','—')}%\n"
                f"• Info Ratio {_nv(ir)} · Tracking err {m.get('tracking_error_pct','—')}%\n"
                f"• Treynor {_nv(tr)}% · Up-cap {m.get('up_capture_pct','—')}% · Down-cap {m.get('down_capture_pct','—')}%\n\n"
                f"<b>Motor cuantitativo</b>\n"
                f"• momentum {_nv(sc.get('momentum_score'))} · valor {_nv(sc.get('value_score'))}\n"
            )
            bd = d.get("score_breakdown") or {}
            if bd:
                top = list(bd.items())[:4]
                header += "• Criterios: " + " · ".join(f"{k} {v:+.2f}" for k, v in top)
            await self.notifier.send_html(header)

            # Each chart as a separate photo (drawdown / vol / vs-benchmark are key for a broker)
            charts = d.get("charts", {}) or {}
            for key, caption in [
                ("price_with_smas", "Precio · SMA50 · SMA200"),
                ("drawdown", "Drawdown histórico"),
                ("returns_histogram", "Distribución de retornos diarios"),
                ("rolling_volatility", "Volatilidad rodante 60d"),
                ("rolling_sharpe", "Sharpe rodante 60d"),
                ("relative_vs_benchmark", f"Rendimiento vs {bench}"),
            ]:
                url = charts.get(key)
                if url:
                    await self.notifier.send_chat_action("upload_photo")
                    await self.notifier.send_photo(url, caption=f"📈 {caption}")

            # News digest (multi-source, with sentiment)
            news = d.get("news") or []
            if news:
                sent = d.get("news_sentiment") or {}
                sources = d.get("news_sources") or []
                lines = [
                    f"📰 <b>Noticias del activo</b>",
                    f"<i>🟢 {sent.get('bullish',0)} · 🔴 {sent.get('bearish',0)} · ⚪ {sent.get('neutral',0)}"
                    + (f" · fuentes: {html_escape(', '.join(sources))}" if sources else "") + "</i>",
                ]
                emj = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}
                for n in news[:6]:
                    e = emj.get(n.get("impact", "neutral"), "⚪")
                    title = html_escape((n.get("title", "") or "")[:140])
                    src = html_escape(n.get("source", ""))
                    url = n.get("url", "")
                    lines.append(f"{e} <a href=\"{url}\">{title}</a> <i>({src})</i>" if url
                                 else f"{e} {title} <i>({src})</i>")
                await self.notifier.send_html("\n".join(lines))

            # Broker-style narrative
            if d.get("narrative"):
                await self.notifier.send_html(
                    f"🖋️ <b>Nota del analista</b>\n\n<i>{html_escape(d['narrative'][:3000])}</i>{PAGE_LINK}"
                )
        except ValueError as exc:
            await self.notifier.send_html(
                f"❌ <b>{html_escape(ticker)}</b> sin datos suficientes en Yahoo "
                f"(<i>{html_escape(str(exc))}</i>). Comprueba el ticker: ¿quizás querías otro? "
                f"Ejemplos válidos: <code>PLTR</code>, <code>SOXX</code>, <code>BTC-USD</code>, "
                f"<code>0P0001DFE8.F</code> (Horos Value)."
            )
        except Exception as exc:
            logger.error("telegram deep analysis failed for {}: {}", ticker, exc)
            await self.notifier.send_text(f"Fallo al analizar {ticker}; reintenta en un momento.")
        finally:
            thinking.cancel()

    async def _send_plans(self) -> None:
        """How each registered investment plan is performing since inception."""
        await self.notifier.send_chat_action("typing")
        try:
            from app.services.plans import evaluate_plans
            d = await evaluate_plans()
            plans = d.get("plans") or []
            if not plans:
                await self.notifier.send_text("No tienes planes registrados todavía.")
                return
            for p in plans:
                avg = p.get("avg_change_pct")
                avg_s = f"{avg:+.2f}%" if avg is not None else "—"
                lines = [f"📋 <b>Plan: {html_escape(p['name'])}</b> ({html_escape(p['horizon'])}) · {p.get('days_elapsed',0)}d",
                         f"<b>Media del plan: {avg_s}</b>"]
                for h in p.get("holdings", []):
                    chg = h.get("change_pct")
                    cs = f"{chg:+.2f}%" if chg is not None else "—"
                    lines.append(f"• {html_escape(h.get('label') or h['ticker'])} ({h['ticker']}): {cs} "
                                 f"<i>(entró {h.get('entry_price')}{h.get('currency') or ''})</i>")
                await self.notifier.send_html("\n".join(lines))
            await self.notifier.send_html(f"<i>{html_escape(d.get('disclaimer',''))}</i>{PAGE_LINK}")
        except Exception as exc:
            logger.error("telegram plans failed: {}", exc)
            await self.notifier.send_text("No pude cargar tus planes ahora mismo.")

    async def _send_position_review(self) -> None:
        """Objective keep/trim/rotate review per holding (anti-disposition-effect)."""
        await self.notifier.send_text("🔍 Revisando tus posiciones (señales objetivas, sin sesgo de tu precio de entrada)…")
        await self.notifier.send_chat_action("typing")
        try:
            from app.services.position_review import review_portfolio
            d = await review_portfolio()
            reviews = d.get("reviews") or []
            if not reviews:
                await self.notifier.send_text("No tengo posiciones que revisar.")
                return
            emoji = {"ROTAR": "🔴", "REDUCIR": "🟠", "VIGILAR": "🟡", "MANTENER": "🟢", "SIN_DATOS": "⚪"}
            s = d.get("summary", {})
            att = s.get('attention_eur', 0) or 0
            head = (f"🔍 <b>Revisión de tu cartera</b>\n"
                    f"🔴 Rotar {s.get('rotar',0)} · 🟠 Reducir {s.get('reducir',0)} · "
                    f"🟡 Vigilar {s.get('vigilar',0)} · 🟢 Mantener {s.get('mantener',0)}\n"
                    f"💰 Dinero que pide atención: <b>{att:,.0f}€</b>")
            await self.notifier.send_html(head)
            # Skip the noise: don't spam a message per insignificant 2€ position.
            shown = [r for r in reviews if not r.get("immaterial")]
            for r in shown:
                e = emoji.get(r["signal"], "⚪")
                m = r.get("metrics") or {}
                lines = [
                    f"{e} <b>{html_escape(r['name'])}</b> ({html_escape(r['ticker'])}) — <b>{r['signal']}</b>",
                    f"<i>Invertido {r.get('invested_eur',0):,.0f}€ → {r.get('value_eur',0):,.0f}€ "
                    f"({r.get('pnl_pct',0):+.1f}%) · peso {r.get('weight_pct',0):.0f}%</i>",
                ]
                for reason in r.get("reasons", [])[:3]:
                    lines.append(f"• {html_escape(reason)}")
                if r.get("bias_flag"):
                    lines.append(html_escape(r["bias_flag"]))
                await self.notifier.send_html("\n".join(lines))
            await self.notifier.send_html(f"<i>{html_escape(d.get('disclaimer',''))}</i>{PAGE_LINK}")
        except Exception as exc:
            logger.error("telegram position review failed: {}", exc)
            await self.notifier.send_text("No pude revisar tus posiciones ahora mismo.")

    async def _send_scorecard(self) -> None:
        """How the engine's past recommendations actually performed (out-of-sample)."""
        await self.notifier.send_chat_action("typing")
        try:
            from app.services.scorecard import summary
            d = await summary()
            total = d.get("total_recommendations_tracked", 0)
            evald = d.get("evaluated_any", 0)
            if total == 0:
                await self.notifier.send_html(
                    "📊 <b>Scorecard del sistema</b>\n\nAún no hay recomendaciones registradas. "
                    "Se irán acumulando cada día; el rendimiento out-of-sample necesita semanas para ser fiable."
                )
                return
            lines = [
                "📊 <b>Scorecard del sistema (out-of-sample)</b>",
                f"<i>{total} recomendaciones seguidas · {evald} ya con resultado a 1 mes</i>",
                "",
            ]
            for key in ("ret_1m", "ret_3m", "ret_6m"):
                h = d["horizons"][key]
                ret, alpha = h.get("return"), h.get("alpha_vs_benchmark")
                if not ret:
                    lines.append(f"<b>{h['label']}:</b> aún sin datos (no han madurado)")
                    continue
                a = f" · alpha {alpha['avg']:+.1f}%" if alpha else ""
                lines.append(
                    f"<b>{h['label']}</b> (n={ret['n']}): retorno medio {ret['avg']:+.1f}% · "
                    f"aciertos {ret['hit_rate_pct']:.0f}%{a}"
                )
            # Approach breakdown at 3m
            ba = d.get("by_approach_3m") or {}
            if any(v for v in ba.values()):
                lines.append("\n<b>Por enfoque (3m):</b>")
                for k, v in ba.items():
                    if v:
                        lines.append(f"• {k}: {v['avg']:+.1f}% · aciertos {v['hit_rate_pct']:.0f}% (n={v['n']})")
            lines.append("\n<i>Es el rendimiento DESPUÉS de recomendar, no promesa futura. "
                         "Necesita historial para ser significativo.</i>")
            await self.notifier.send_html("\n".join(lines) + PAGE_LINK)
        except Exception as exc:
            logger.error("telegram scorecard failed: {}", exc)
            await self.notifier.send_text("No pude generar el scorecard ahora mismo.")

    async def _send_news_digest(self) -> None:
        """Send the top recent headlines with sentiment + source + link."""
        await self.notifier.send_chat_action("typing")
        try:
            from app.services.news import NewsService
            items = (await NewsService().get_news("all", limit=10))[:8]
            if not items:
                await self.notifier.send_text("No pude cargar noticias ahora mismo.")
                return
            emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}
            lines = ["📰 <b>Titulares recientes</b>"]
            for n in items:
                em = emoji.get(n.get("impact", "neutral"), "⚪")
                title = html_escape((n.get("title", "") or "")[:140])
                src = html_escape(n.get("source", ""))
                url = n.get("url", "")
                lines.append(f"{em} <a href=\"{url}\">{title}</a> <i>({src})</i>" if url
                             else f"{em} {title} <i>({src})</i>")
            await self.notifier.send_html("\n".join(lines))
        except Exception as exc:
            logger.error("telegram news digest failed: {}", exc)
            await self.notifier.send_text("No pude cargar noticias ahora mismo.")

    async def _send_briefing(self) -> None:
        """Send today's AI briefing (cached / generates if needed)."""
        await self.notifier.send_chat_action("typing")
        try:
            from app.services.briefing import BriefingService
            res = await BriefingService().generate_today()
            head = res.get("headline") or "Briefing del día"
            body = res.get("summary_markdown") or ""
            await self.notifier.send_html(f"📋 <b>{html_escape(head)}</b>\n\n{html_escape(body[:3000])}{PAGE_LINK}")
        except Exception as exc:
            logger.error("telegram briefing failed: {}", exc)
            await self.notifier.send_text("No pude preparar el briefing ahora mismo.")

    async def _send_market_state(self) -> None:
        """Quick read of the current market regime from the cached opportunities scan."""
        try:
            from app.services.opportunities import get_opportunity_service
            svc = get_opportunity_service()
            payload = svc._cache or (await svc._load_from_db())  # don't trigger a 2-min scan here
            if not payload:
                await self.notifier.send_text(
                    "Aún no tengo lectura reciente del mercado. Prueba /oportunidades para forzar el análisis."
                )
                return
            regime = payload.get("market_regime") or "neutral"
            breadth = payload.get("market_breadth")
            em = {"alcista": "🟢", "bajista": "🔴", "neutral": "🟡"}.get(regime, "🟡")
            pct = f" ({round(breadth * 100)}% sobre su tendencia 200d)" if breadth is not None else ""
            patterns = (payload.get("trends") or {}).get("patterns") or []
            extra = ("\n\n<b>Patrones detectados:</b>\n• " + "\n• ".join(patterns[:3])) if patterns else ""
            await self.notifier.send_html(
                f"{em} <b>Régimen de mercado:</b> {regime}{pct}.{extra}{PAGE_LINK}"
            )
        except Exception as exc:
            logger.error("telegram market state failed: {}", exc)
            await self.notifier.send_text("No pude leer el estado del mercado ahora mismo.")

    async def _send_chart(self, text: str) -> None:
        """Send a portfolio or per-asset evolution chart as an image."""
        await self.notifier.send_chat_action("upload_photo")
        low = text.lower()
        async with session_scope() as session:
            positions = await PositionRepository(session).list_all()

        # Did they mention a specific asset?
        target = self._match_position(text, positions)
        try:
            if target:
                period_days = 180
                history = await self.portfolio_service.get_asset_history(
                    target.ticker, target.type, days=period_days
                )
                if not history:
                    await self.notifier.send_text(
                        f"No pude obtener el histórico de {friendly_name(target.ticker, target.asset_name)} ahora mismo."
                    )
                    return
                labels = [h["date"] for h in history]
                values = [h.get("close") or h.get("price") for h in history]
                name = friendly_name(target.ticker, target.asset_name)
                url = line_chart(f"{name} — últimos 6 meses", labels, values)
                await self.notifier.send_photo(url, caption=f"📈 <b>{html_escape(name)}</b>{PAGE_LINK}")
            else:
                # Portfolio evolution
                hist = await self.portfolio_service.get_portfolio_history(days=180)
                if not hist or len(hist) < 2:
                    await self.notifier.send_html(
                        "Aún no tengo suficiente histórico de tu cartera para una gráfica "
                        "(se va construyendo cada día)." + PAGE_LINK
                    )
                    return
                labels = [h["date"] for h in hist]
                values = [h["value"] for h in hist]
                url = line_chart("Evolución de tu cartera", labels, values)
                await self.notifier.send_photo(url, caption=f"📊 <b>Tu cartera</b>{PAGE_LINK}")
        except Exception as exc:
            logger.error("telegram chart failed: {}", exc)
            await self.notifier.send_text("No pude generar la gráfica ahora mismo, intenta en un momento.")

    # ------------------------------------------------------------------ helpers

    def _looks_like_contribution(self, low: str) -> bool:
        has_kw = any(k in low for k in CONTRIBUTE_KEYWORDS)
        has_amount = re.search(r"\d+([.,]\d+)?\s*(€|eur|euros?)", low) is not None
        return has_kw and has_amount

    async def _send_quick_summary(self) -> None:
        p = await self.portfolio_service.calculate_portfolio()
        lines = [
            f"💼 <b>Tu cartera</b>: {p['total_value']:.2f} {p['base_currency']}",
            f"P/L total: {p['total_gain_loss']:+.2f} € ({p['total_gain_loss_pct']:+.2f}%)",
            f"Hoy: {p['daily_change']:+.2f} € ({p['daily_change_pct']:+.2f}%)",
            "",
            "<b>Posiciones:</b>",
        ]
        for pos in p["positions"][:12]:
            name = friendly_name(pos["ticker"], pos.get("name"))
            day = pos.get("day_change_pct", 0) or 0
            mark = "🟢" if day >= 0 else "🔴"
            lines.append(
                f"• {html_escape(name)}: {pos['market_value_base']:.2f} € "
                f"· hoy {mark}{day:+.1f}% · P/L {pos['gain_loss_pct']:+.1f}%"
            )
        lines.append(PAGE_LINK)
        await self.notifier.send_html("\n".join(lines))

    async def _try_contribution(self, text: str) -> bool:
        """Parse and execute a contribution. Returns True if handled."""
        async with session_scope() as session:
            positions = await PositionRepository(session).list_all()

        if not positions:
            await self.notifier.send_text("No tienes posiciones en las que aportar todavía.")
            return True

        # Amount
        m_amt = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:€|eur|euros?)?", text)
        amount = None
        if m_amt:
            try:
                amount = float(m_amt.group(1).replace(",", "."))
            except ValueError:
                amount = None

        # Match a position by ticker, ISIN, or a friendly alias
        target = self._match_position(text, positions)

        if not target or not amount:
            await self.notifier.send_html(
                "No pude identificar el fondo o el importe. Prueba: "
                "<code>/aportar &lt;fondo&gt; &lt;euros&gt;</code>\n"
                f"Fondos disponibles: {', '.join(sorted({p.ticker for p in positions}))}"
            )
            return True

        # Execute via the same logic as the HTTP endpoint
        from app.api.positions import _current_price
        from app.repositories import TransactionRepository
        from datetime import datetime, timezone

        price = await _current_price(target.ticker, target.type)
        if not price:
            await self.notifier.send_text(f"No pude obtener el precio de {target.ticker} ahora mismo.")
            return True

        shares_added = amount / price
        async with session_scope() as session:
            repo = PositionRepository(session)
            pos = await repo.get(target.ticker, target.broker)
            old_cost = pos.quantity * pos.avg_price
            pos.quantity += shares_added
            pos.avg_price = (old_cost + amount) / pos.quantity
            await session.flush()
            try:
                await TransactionRepository(session).add(
                    type="buy", ticker=pos.ticker, quantity=shares_added, price=price,
                    currency=pos.currency, broker=pos.broker,
                    executed_at=datetime.now(timezone.utc),
                    notes=f"Aportación Telegram {amount:.2f}€",
                )
            except Exception:
                pass

        await self.notifier.send_html(
            f"✅ Aportados <b>{amount:.2f} €</b> a <b>{html_escape(target.ticker)}</b>\n"
            f"Precio hoy: {price:.4f} € · +{shares_added:.6f} participaciones\n"
            f"Nueva cantidad: {pos.quantity:.6f}"
        )
        return True

    def _match_position(self, text: str, positions):
        low = text.lower()
        # Friendly aliases → match against asset_name / ticker
        aliases = {
            "oro": ["gold", "ie00b4nd3602", "ppfb"],
            "gold": ["ie00b4nd3602"],
            "nasdaq": ["lyx0f", "nasdaq", "ust"],
            "world": ["msci world", "ie00byx5nx33", "fidelity"],
            "msci": ["ie00byx5nx33"],
            "btc": ["btc", "bitcoin"],
            "bitcoin": ["btc"],
            "eth": ["eth", "ethereum"],
            "ethereum": ["eth"],
            "sol": ["sol", "solana"],
            "solana": ["sol"],
            "doge": ["doge", "dogecoin"],
            "pepe": ["pepe"],
        }
        # Direct ticker/ISIN match
        for p in positions:
            if p.ticker.lower() in low:
                return p
        # Alias match
        for alias, needles in aliases.items():
            if alias in low:
                for p in positions:
                    hay = f"{p.ticker} {p.asset_name or ''}".lower()
                    if p.ticker.lower() == alias or any(n in hay for n in needles):
                        return p
        # Asset name word match
        for p in positions:
            name = (p.asset_name or "").lower()
            if name and any(w in low for w in name.split() if len(w) > 3):
                return p
        return None

    async def _answer_question(self, question: str) -> None:
        settings = self.settings
        if not settings.has_gemini and not settings.has_groq:
            await self.notifier.send_text("No tengo LLM configurado para responder ahora mismo.")
            return

        # Show "escribiendo..." while we crunch the portfolio + call the LLM
        await self.notifier.send_chat_action("typing")

        # Build rich context: portfolio + weekly change + per-position detail
        try:
            p = await self.portfolio_service.calculate_portfolio()
        except Exception as exc:
            logger.warning("telegram Q&A: portfolio failed: {}", exc)
            await self.notifier.send_text("No pude cargar tu cartera ahora mismo, intenta en un minuto.")
            return

        await self.notifier.send_chat_action("typing")

        # Weekly change from snapshots
        weekly_line = ""
        try:
            async with session_scope() as session:
                snaps = await SnapshotRepository(session).list_last_days(days=8)
            if len(snaps) >= 2:
                wk_ago = snaps[0].total_value
                now = snaps[-1].total_value
                if wk_ago > 0:
                    pct = (now - wk_ago) / wk_ago * 100
                    weekly_line = f"\nCambio última semana: {now - wk_ago:+.2f} € ({pct:+.2f}%)"
        except Exception:
            pass

        context = [
            f"Cartera: valor actual {p['total_value']:.2f} {p['base_currency']} | "
            f"dinero invertido (coste) {p['total_cost']:.2f}€ | "
            f"ganancia/pérdida total {p['total_gain_loss']:+.2f}€ ({p['total_gain_loss_pct']:+.2f}%) | "
            f"hoy {p['daily_change']:+.2f}€ ({p['daily_change_pct']:+.2f}%){weekly_line}",
            "",
            "Posiciones (invertido = lo que pusiste; valor = lo que vale hoy; ganancia = valor - invertido):",
        ]
        for pos in p["positions"]:
            name = friendly_name(pos["ticker"], pos.get("name"))
            invested = pos.get("cost_basis", 0)
            gain_eur = pos.get("gain_loss", 0)
            context.append(
                f"- {name} (ticker {pos['ticker']}, {pos['type']}, {pos['broker']}): "
                f"{pos['quantity']:.6g} unidades · invertido {invested:.2f}€ · "
                f"valor actual {pos['market_value_base']:.2f}€ · "
                f"ganancia {gain_eur:+.2f}€ ({pos['gain_loss_pct']:+.1f}%) · "
                f"hoy {pos['day_change_pct']:+.1f}% · peso {pos['weight']:.1f}%"
            )
        context_str = "\n".join(context)

        # Enrich context with recent news + market regime (best-effort, never blocks)
        news_block = ""
        try:
            from app.services.news import NewsService
            ns = (await NewsService().get_news("all", limit=6))[:6]
            if ns:
                news_block = "\n\nTITULARES RECIENTES:\n" + "\n".join(
                    f"- [{n.get('impact','neutral')}] {(n.get('title','') or '')[:140]} ({n.get('source','')})"
                    for n in ns
                )
        except Exception:
            pass
        market_block = ""
        try:
            from app.services.opportunities import get_opportunity_service
            svc = get_opportunity_service()
            cached = svc._cache or (await svc._load_from_db())
            if cached:
                rg = cached.get("market_regime")
                br = cached.get("market_breadth")
                if rg:
                    market_block = f"\n\nRÉGIMEN DE MERCADO: {rg}" + (f" ({round(br*100)}% sobre 200d)" if br is not None else "")
        except Exception:
            pass

        system = (
            "Eres FinBot, asistente financiero personal del usuario por Telegram. Respondes en español, "
            "BREVE y claro (se lee en el móvil). Tienes tres tipos de información: (1) los DATOS DE LA "
            "CARTERA del usuario, (2) TITULARES de noticias recientes, (3) el RÉGIMEN del mercado.\n\n"
            "Tu trabajo: responder cualquier pregunta razonable de inversión usando ESA información y "
            "conocimiento general (conceptos como Sharpe, momentum, ETFs, etc.). NO inventes datos que no "
            "tengas. Si el usuario pide IDEAS o RECOMENDACIONES concretas de qué comprar, dile que pulse "
            "/oportunidades (el motor cuantitativo le dará un análisis completo). Si pide una GRÁFICA, "
            "que use 'gráfica de [activo]'. Si quiere REGISTRAR una aportación, que diga 'mete X€ a [activo] "
            "desde [broker]'.\n\n"
            "Sobre la cartera: TIENES el campo 'invertido' (= cantidad × precio medio), el valor actual y la "
            "ganancia en € de cada activo. Úsalos. NUNCA digas que no sabes el dinero invertido. Refiérete "
            "a los activos por su NOMBRE (Oro físico, Nasdaq-100, Fidelity MSCI World), no por ISIN. "
            "Asocia 'el oro', 'el nasdaq', 'el msci' al activo correcto.\n\n"
            "No des órdenes de compra/venta. Sé honesto si una pregunta requiere datos que no tienes "
            "(ej. precio en tiempo real de algo que no está en la cartera) y sugiere cómo obtenerlos. "
            "En cripto el 'invertido' es el precio medio de Kraken; en fondos es estimado."
        )
        full_context = f"DATOS DE LA CARTERA:\n{context_str}{news_block}{market_block}"
        try:
            client = get_llm_client()
            resp = await client.generate(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=f"{full_context}\n\nPREGUNTA: {question}"),
                ],
                max_tokens=800,
                temperature=0.4,
            )
            answer = resp.text.strip() or "No tengo una respuesta ahora mismo."
            await self.notifier.send_html(html_escape(answer[:3400]) + PAGE_LINK)
        except Exception as exc:
            logger.error("telegram Q&A LLM failed: {}", exc)
            await self.notifier.send_text(f"No pude responder: {str(exc)[:100]}")
