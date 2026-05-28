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

        if low in ("/oportunidades", "oportunidades", "ideas", "recomendaciones", "que compro", "qué compro"):
            await self._send_opportunities()
            return

        # Natural-language "what should I invest in?" → opportunities (must come
        # BEFORE the contribution intent, since "invierto" overlaps both).
        if any(p in low for p in OPPORTUNITY_QUERY_PATTERNS):
            await self._send_opportunities()
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
                await self.notifier.send_html(
                    f"💡 <b>Oportunidades del día</b>{regime_line}\n\n<i>{payload['market_summary']}</i>"
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
            lines.append(
                f"• {html_escape(name)}: {pos['market_value_base']:.2f} € "
                f"({pos['gain_loss_pct']:+.1f}%)"
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
