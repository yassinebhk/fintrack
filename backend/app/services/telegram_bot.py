"""Inbound Telegram message handler — makes the bot conversational.

Two capabilities:
1. Answer questions about the portfolio (delegates to FinBot / LLM with rich context).
2. Add money to a fund via natural language or /aportar command.

Security: only the configured TELEGRAM_CHAT_ID is allowed to interact.
"""

import re
from datetime import date, timedelta

from loguru import logger

from app.config import get_settings
from app.db import session_scope
from app.llm import LLMMessage, get_llm_client
from app.repositories import PositionRepository, SnapshotRepository
from app.services.notifications.telegram import TelegramNotifier, html_escape
from app.services.portfolio import PortfolioService


HELP_TEXT = (
    "🤖 <b>FinBot</b> — tu asistente de cartera\n\n"
    "Puedes:\n"
    "• Preguntarme cualquier cosa: <i>¿cuánto he ganado esta semana?</i>, "
    "<i>resumen de mi bitcoin</i>, <i>¿cómo está diversificada mi cartera?</i>\n"
    "• Aportar dinero a un fondo: <code>/aportar oro 50</code> o "
    "<i>he metido 50€ al nasdaq</i>\n"
    "• <code>/cartera</code> — resumen rápido\n"
    "• <code>/ayuda</code> — este mensaje"
)

CONTRIBUTE_KEYWORDS = ("aporta", "aporté", "aporte", "mete", "metí", "meti", "añad", "anad",
                       "invierto", "invertí", "inverti", "compr", "ingreso", "ingresé")


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

        # Contribution intent?
        if low.startswith("/aportar") or self._looks_like_contribution(low):
            handled = await self._try_contribution(text)
            if handled:
                return
            # fall through to Q&A if we couldn't parse it

        # Otherwise treat as a question for FinBot
        await self._answer_question(text)

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
            lines.append(
                f"• {html_escape(pos['ticker'])}: {pos['market_value_base']:.2f} € "
                f"({pos['gain_loss_pct']:+.1f}%)"
            )
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

        # Build rich context: portfolio + weekly change + per-position detail
        try:
            p = await self.portfolio_service.calculate_portfolio()
        except Exception as exc:
            logger.warning("telegram Q&A: portfolio failed: {}", exc)
            await self.notifier.send_text("No pude cargar tu cartera ahora mismo, intenta en un minuto.")
            return

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
            f"Cartera: {p['total_value']:.2f} {p['base_currency']} | "
            f"P/L total {p['total_gain_loss']:+.2f} ({p['total_gain_loss_pct']:+.2f}%) | "
            f"hoy {p['daily_change']:+.2f} ({p['daily_change_pct']:+.2f}%){weekly_line}",
            "",
            "Posiciones:",
        ]
        for pos in p["positions"]:
            context.append(
                f"- {pos['ticker']} ({pos['type']}, {pos['broker']}): {pos['quantity']:.6g} ud, "
                f"valor {pos['market_value_base']:.2f}€, P/L {pos['gain_loss_pct']:+.1f}%, "
                f"hoy {pos['day_change_pct']:+.1f}%, peso {pos['weight']:.1f}%"
            )
        context_str = "\n".join(context)

        system = (
            "Eres FinBot, asistente financiero del usuario por Telegram. Respondes en español, "
            "breve y claro (esto se lee en el móvil). Usas SOLO los datos de la cartera que se te dan. "
            "Si te piden algo que no está en los datos, dilo. No das consejos de compra/venta concretos."
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
            # Telegram HTML: send plain (LLM may emit markdown); keep it simple
            await self.notifier.send_text(answer[:3500])
        except Exception as exc:
            logger.error("telegram Q&A LLM failed: {}", exc)
            await self.notifier.send_text(f"No pude responder: {str(exc)[:100]}")
