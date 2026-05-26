"""Briefing service — runs the agent pipeline and persists the result."""

import asyncio
from datetime import date, datetime, timezone

from loguru import logger

from app.agents import (
    AgentContext,
    CryptoAgent,
    MarketAgent,
    NewsAgent,
    OrchestratorAgent,
    RiskAgent,
)
from app.db import session_scope
from app.models.briefing import Briefing
from app.services.news import NewsService
from app.services.portfolio import PortfolioService
from app.services.notifications.telegram import TelegramNotifier


def render_briefing_markdown(content: dict) -> str:
    lines = []
    headline = content.get("headline", "Briefing diario")
    lines.append(f"# {headline}\n")
    for section in content.get("sections", []):
        lines.append(f"## {section.get('title', '?')}")
        lines.append(section.get("body", ""))
        lines.append("")
    action = content.get("suggested_action") or {}
    if action:
        lines.append(f"**Acción sugerida**: `{action.get('label', '-')}` — {action.get('rationale', '')}")
        lines.append("")
    if content.get("disclaimer"):
        lines.append(f"_{content['disclaimer']}_")
    return "\n".join(lines).strip()


SECTION_ICONS = {
    "cartera": "💼",
    "portfolio": "💼",
    "mercados": "🌍",
    "mercado": "🌍",
    "market": "🌍",
    "vigilar": "👀",
    "watch": "👀",
    "noticias": "📰",
    "news": "📰",
    "riesgo": "⚠️",
    "risk": "⚠️",
    "cripto": "₿",
    "crypto": "₿",
}

ACTION_LABELS = {
    "dca": "Continuar DCA",
    "rebalance": "Rebalancear cartera",
    "hold": "Mantener posiciones",
    "watch": "Vigilar mercado",
    "review_risk": "Revisar exposición al riesgo",
    "none": "Sin acción",
}


def _section_icon(title: str) -> str:
    if not title:
        return "•"
    key = title.lower()
    for needle, icon in SECTION_ICONS.items():
        if needle in key:
            return icon
    return "•"


def render_briefing_telegram(content: dict, briefing_date=None) -> str:
    """Telegram HTML rendering — visually rich, predictable parser.

    Telegram HTML supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a>, <tg-spoiler>.
    Only &, <, > need escaping in content.
    """
    from datetime import date as _date
    from app.services.notifications.telegram import html_escape as esc

    briefing_date = briefing_date or _date.today()
    date_str = briefing_date.strftime("%d %b %Y").capitalize()

    parts: list[str] = []

    # Header
    parts.append(f"📊 <b>FinTrack — Briefing diario</b>")
    parts.append(f"<i>{esc(date_str)}</i>")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━━━━")

    # Headline
    headline = content.get("headline")
    if headline:
        parts.append(f"<b>{esc(headline)}</b>")
        parts.append("")

    # Sections
    for section in content.get("sections", []):
        title = section.get("title", "")
        body = section.get("body", "")
        if not title and not body:
            continue
        icon = _section_icon(title)
        parts.append(f"{icon} <b>{esc(title)}</b>")
        parts.append(esc(body))
        parts.append("")

    # Suggested action
    action = content.get("suggested_action") or {}
    if action:
        label = action.get("label", "none")
        label_pretty = ACTION_LABELS.get(label, label)
        rationale = action.get("rationale", "")
        parts.append("━━━━━━━━━━━━━━━━━━")
        parts.append(f"🎯 <b>Acción sugerida:</b> <i>{esc(label_pretty)}</i>")
        if rationale:
            parts.append(esc(rationale))
        parts.append("")

    # Disclaimer
    if content.get("disclaimer"):
        parts.append(f"<i>{esc(content['disclaimer'])}</i>")

    return "\n".join(parts).strip()


class BriefingService:
    def __init__(self) -> None:
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self.telegram = TelegramNotifier()

    async def generate_today(self, *, force: bool = False) -> dict:
        """Run agent pipeline, persist result, return content dict."""
        today = date.today()

        existing = await self._get_today(today)
        if existing and not force:
            logger.info("briefing for {} already exists; returning cached", today)
            return self._existing_to_dict(existing)

        portfolio = await self.portfolio_service.calculate_portfolio()
        news_items = await self.news_service.get_news("all", limit=30)

        context_base = AgentContext(portfolio=portfolio)
        market = MarketAgent()
        news = NewsAgent()
        risk = RiskAgent()
        crypto = CryptoAgent()

        news_ctx = AgentContext(portfolio=portfolio, extras={"news": news_items})
        crypto_ctx = AgentContext(portfolio=portfolio, extras={"crypto_market": {}})

        try:
            market_res, news_res, risk_res, crypto_res = await asyncio.gather(
                market.run(context_base),
                news.run(news_ctx),
                risk.run(context_base),
                crypto.run(crypto_ctx),
                return_exceptions=False,
            )
        except Exception as exc:
            logger.exception("specialist agents failed")
            raise

        sub_results = {
            "market": market_res.output,
            "news": news_res.output,
            "risk": risk_res.output,
            "crypto": crypto_res.output,
        }
        total_tokens_in = sum(r.tokens_input for r in (market_res, news_res, risk_res, crypto_res))
        total_tokens_out = sum(r.tokens_output for r in (market_res, news_res, risk_res, crypto_res))

        orch = OrchestratorAgent()
        orch_ctx = AgentContext(portfolio=portfolio, extras={"sub_results": sub_results})
        orch_res = await orch.run(orch_ctx)
        content = orch_res.output

        total_tokens_in += orch_res.tokens_input
        total_tokens_out += orch_res.tokens_output

        markdown = render_briefing_markdown(content)
        await self._persist(
            today=today,
            content=content,
            sub_results=sub_results,
            markdown=markdown,
            model=orch_res.model,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )

        delivered = await self.telegram.send_html(render_briefing_telegram(content, briefing_date=today))
        if delivered:
            await self._mark_delivered(today)

        return {
            "date": today.isoformat(),
            "content": content,
            "markdown": markdown,
            "model": orch_res.model,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "delivered_telegram": delivered,
        }

    async def _get_today(self, today: date) -> Briefing | None:
        from sqlalchemy import select

        async with session_scope() as session:
            result = await session.execute(select(Briefing).where(Briefing.briefing_date == today))
            return result.scalar_one_or_none()

    async def _persist(
        self,
        *,
        today: date,
        content: dict,
        sub_results: dict,
        markdown: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        async with session_scope() as session:
            existing = await self._get_today(today)
            if existing:
                existing.headline = content.get("headline", "")
                existing.summary_markdown = markdown
                existing.content_json = {"content": content, "sub_results": sub_results}
                existing.model = model
                existing.tokens_input = tokens_in
                existing.tokens_output = tokens_out
                session.add(existing)
            else:
                row = Briefing(
                    briefing_date=today,
                    headline=content.get("headline", ""),
                    summary_markdown=markdown,
                    content_json={"content": content, "sub_results": sub_results},
                    model=model,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                )
                session.add(row)

    async def _mark_delivered(self, today: date) -> None:
        async with session_scope() as session:
            row = await self._get_today(today)
            if row:
                row.delivered_telegram = True
                session.add(row)

    def _existing_to_dict(self, row: Briefing) -> dict:
        payload = row.content_json or {}
        content = payload.get("content", {}) if isinstance(payload, dict) else {}
        return {
            "date": row.briefing_date.isoformat(),
            "content": content,
            "markdown": row.summary_markdown,
            "model": row.model,
            "tokens_in": row.tokens_input,
            "tokens_out": row.tokens_output,
            "delivered_telegram": row.delivered_telegram,
            "cached": True,
        }

    async def get_briefing(self, target: date) -> dict | None:
        from sqlalchemy import select

        async with session_scope() as session:
            result = await session.execute(select(Briefing).where(Briefing.briefing_date == target))
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._existing_to_dict(row)
