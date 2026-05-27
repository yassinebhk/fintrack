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


class OpportunityService:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self._cache: dict | None = None
        self._cache_at: datetime | None = None
        self._ttl = timedelta(hours=12)
        self._lock = asyncio.Lock()

    def _fresh(self) -> bool:
        return (
            self._cache is not None
            and self._cache_at is not None
            and datetime.now(timezone.utc) - self._cache_at < self._ttl
        )

    async def generate(self, *, force: bool = False) -> dict:
        if self._fresh() and not force:
            return self._cache

        # Only one scan at a time: concurrent callers (manual click, daily job, bot)
        # wait for the in-flight result instead of each kicking off a heavy 100+
        # ticker scan and thrashing the instance.
        async with self._lock:
            if self._fresh() and not force:
                return self._cache
            return await self._generate_locked()

    async def _generate_locked(self) -> dict:
        portfolio = await self.portfolio_service.calculate_portfolio()

        # Exclude what the user already holds so discoveries are genuinely new.
        held = set()
        for p in (portfolio.get("positions") or []):
            if p.get("ticker"):
                held.add(str(p["ticker"]).upper())

        # Scan the WIDE universe + Yahoo screeners, ranked objectively by the quant engine.
        themes = await self.scanner.scan_universe(exclude_tickers=held)
        themes_str = self.scanner.render_for_prompt(themes)

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

        opportunities = content.get("opportunities", []) or []
        # Enrich each idea with a 6-month trend chart + the headlines that back it.
        await self._enrich_opportunities(opportunities, news_items)

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
            "model": result.model,
            "themes": top_themes,
            "universe_size": len(themes),
            "market_summary": content.get("market_summary", ""),
            "opportunities": opportunities,
            "disclaimer": content.get("disclaimer", ""),
        }
        self._cache = payload
        self._cache_at = datetime.now(timezone.utc)
        return payload

    async def _enrich_opportunities(
        self, opportunities: list[dict], news_items: list[dict]
    ) -> None:
        """Attach a 6-month trend chart_url and supporting news (with links) to each idea."""
        from app.services.charts import line_chart

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
    news = op.get("news") or []
    if news:
        lines.append("<b>📰 Noticias que lo respaldan:</b>")
        for n in news[:2]:
            title = esc((n.get("title", "") or "")[:110])
            url = n.get("url", "")
            src = esc(n.get("source", ""))
            lines.append(f"• <a href=\"{url}\">{title}</a> <i>({src})</i>" if url else f"• {title} <i>({src})</i>")
    return "\n".join(lines)[:1024]
