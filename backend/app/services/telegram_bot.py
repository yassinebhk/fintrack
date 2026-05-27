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
                OpportunityService,
                render_opportunities_telegram,
                render_opportunity_caption,
            )

            payload = await OpportunityService().generate()
            thinking.cancel()  # done thinking → stop the typing indicator
            opps = payload.get("opportunities") or []
            if not opps:
                await self.notifier.send_text("No pude generar oportunidades ahora mismo (posible límite de cuota). Reintenta en un rato.")
                return

            # Market summary first, then one trend chart per idea (with the news that backs it).
            if payload.get("market_summary"):
                await self.notifier.send_html(f"💡 <b>Oportunidades del día</b>\n\n<i>{payload['market_summary']}</i>")
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

        system = (
            "Eres FinBot, asistente financiero del usuario por Telegram. Respondes en español, "
            "breve y claro (esto se lee en el móvil). Usas SOLO los datos de la cartera que se te dan. "
            "TIENES el dinero invertido (campo 'invertido' = cantidad × precio medio de compra), el valor "
            "actual y la ganancia en € de cada activo y del total: úsalos para responder cuánto invirtió, "
            "cuánto vale y cuánto ha ganado. NUNCA digas que no sabes el dinero invertido — está en los datos. "
            "Refiérete a los activos por su NOMBRE (ej. 'Oro físico', 'Nasdaq-100', 'Fidelity MSCI World'), "
            "no por su ISIN. Si te preguntan por 'el oro', 'el nasdaq', 'el msci', etc., asócialo al activo "
            "correcto. No das consejos de compra/venta concretos. "
            "Aclara, solo si es relevante, que en cripto el 'invertido' es el precio medio de Kraken y en "
            "fondos es una estimación basada en el precio medio."
        )
        try:
            client = get_llm_client()
            resp = await client.generate(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=f"DATOS DE LA CARTERA:\n{context_str}\n\nPREGUNTA: {question}"),
                ],
                max_tokens=800,
                temperature=0.4,
            )
            answer = resp.text.strip() or "No tengo una respuesta ahora mismo."
            await self.notifier.send_html(html_escape(answer[:3400]) + PAGE_LINK)
        except Exception as exc:
            logger.error("telegram Q&A LLM failed: {}", exc)
            await self.notifier.send_text(f"No pude responder: {str(exc)[:100]}")
