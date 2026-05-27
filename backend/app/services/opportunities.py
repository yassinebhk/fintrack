"""Opportunity discovery service — runs the market scanner + analyst agent."""

from datetime import datetime, timedelta, timezone

from loguru import logger

from app.agents.analyst_agent import AnalystAgent
from app.agents.base import AgentContext
from app.services.discovery import MarketScanner
from app.services.market import ECBClient, FREDClient
from app.services.news import NewsService
from app.services.portfolio import PortfolioService


class OpportunityService:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self._cache: dict | None = None
        self._cache_at: datetime | None = None
        self._ttl = timedelta(hours=12)

    def _fresh(self) -> bool:
        return (
            self._cache is not None
            and self._cache_at is not None
            and datetime.now(timezone.utc) - self._cache_at < self._ttl
        )

    async def generate(self, *, force: bool = False) -> dict:
        if self._fresh() and not force:
            return self._cache

        themes = await self.scanner.scan_themes()
        themes_str = self.scanner.render_for_prompt(themes)

        # Macro context (best-effort)
        us_macro, eu_macro = [], []
        try:
            us_macro = await FREDClient().snapshot()
            eu_macro = await ECBClient().snapshot()
        except Exception as exc:
            logger.warning("opportunities macro fetch partial: {}", exc)

        portfolio = await self.portfolio_service.calculate_portfolio()

        # Recent news (already sentiment-classified by LLM) to give the analyst current context
        news_str = ""
        try:
            news = await self.news_service.get_news("all", limit=25)
            lines = ["Titulares recientes (con sentimiento):"]
            for n in news[:25]:
                lines.append(f"- [{n.get('source')}|{n.get('impact','neutral')}] {n.get('title','')[:160]}")
            news_str = "\n".join(lines)
        except Exception as exc:
            logger.warning("opportunities news fetch failed: {}", exc)

        ctx = AgentContext(
            portfolio=portfolio,
            extras={
                "themes_str": themes_str,
                "macro": {"us": us_macro, "eu": eu_macro},
                "news_str": news_str,
            },
        )
        result = await AnalystAgent().run(ctx)
        content = result.output

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": result.model,
            "themes": themes,
            "market_summary": content.get("market_summary", ""),
            "opportunities": content.get("opportunities", []),
            "disclaimer": content.get("disclaimer", ""),
        }
        self._cache = payload
        self._cache_at = datetime.now(timezone.utc)
        return payload


def render_opportunities_telegram(payload: dict) -> str:
    from app.services.notifications.telegram import html_escape as esc

    parts = ["💡 <b>Oportunidades del día</b>", ""]
    if payload.get("market_summary"):
        parts.append(f"<i>{esc(payload['market_summary'])}</i>")
        parts.append("")

    conv_emoji = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
    for op in payload.get("opportunities", []):
        emoji = conv_emoji.get(op.get("conviction", "media"), "🟡")
        name = esc(op.get("name", ""))
        kind = esc(op.get("kind", ""))
        tk = op.get("ticker_or_isin")
        header = f"{emoji} <b>{name}</b> ({kind}{', ' + esc(tk) if tk else ''})"
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
