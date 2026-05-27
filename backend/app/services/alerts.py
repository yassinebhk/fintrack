"""Rules engine — evaluates portfolio + news and emits Alert rows + Telegram pushes."""

from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from app.db import session_scope
from app.models.alert import Alert
from app.services.news import NewsService
from app.services.notifications.telegram import TelegramNotifier
from app.services.portfolio import PortfolioService


# Thresholds — overridable later by user preferences
PORTFOLIO_INTRADAY_DROP_PCT = -3.0
ASSET_INTRADAY_DROP_PCT = -7.0
DRAWDOWN_THRESHOLD_PCT = -15.0
DEDUPE_WINDOW_HOURS = 24


class AlertsEngine:
    def __init__(self) -> None:
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self.telegram = TelegramNotifier()

    async def evaluate(self) -> list[dict]:
        """Run all rules. Returns a list of alert payloads created."""
        portfolio = await self.portfolio_service.calculate_portfolio()
        created: list[dict] = []

        # Rule 1: portfolio intraday drop
        daily_pct = portfolio.get("daily_change_pct", 0)
        if daily_pct <= PORTFOLIO_INTRADAY_DROP_PCT:
            created.append(
                await self._maybe_create(
                    kind="portfolio_drop",
                    severity="warning" if daily_pct > -6 else "critical",
                    title=f"Cartera cae {daily_pct:.2f}% hoy",
                    body=(
                        f"Tu cartera está en {portfolio.get('total_value', 0):.2f} "
                        f"{portfolio.get('base_currency', 'EUR')} ({daily_pct:+.2f}% hoy)."
                    ),
                    payload={"daily_change_pct": daily_pct, "total_value": portfolio.get("total_value")},
                    dedupe_key=f"portfolio_drop:{daily_pct:.0f}",
                )
            )

        # Rule 2: individual asset intraday drop
        for pos in portfolio.get("positions", []):
            pct = pos.get("day_change_pct", 0)
            if pct <= ASSET_INTRADAY_DROP_PCT:
                created.append(
                    await self._maybe_create(
                        kind="asset_drop",
                        severity="warning" if pct > -12 else "critical",
                        title=f"{pos['ticker']} cae {pct:.2f}% hoy",
                        body=(
                            f"{pos['ticker']} ({pos.get('type')}, {pos.get('broker')}): "
                            f"precio actual {pos.get('current_price'):.6g} "
                            f"({pct:+.2f}% intradía, peso en cartera {pos.get('weight', 0):.1f}%)."
                        ),
                        payload={"ticker": pos["ticker"], "day_change_pct": pct},
                        dedupe_key=f"asset_drop:{pos['ticker']}",
                    )
                )

        # Rule 3: drawdown from peak
        kpis = portfolio.get("kpis", {})
        max_dd = kpis.get("max_drawdown", 0)
        if max_dd >= abs(DRAWDOWN_THRESHOLD_PCT):
            created.append(
                await self._maybe_create(
                    kind="drawdown",
                    severity="warning",
                    title=f"Drawdown actual: -{max_dd:.2f}% desde el máximo",
                    body=(
                        f"Tu cartera ha caído un -{max_dd:.2f}% desde el máximo histórico "
                        f"(fecha: {kpis.get('max_drawdown_date')})."
                    ),
                    payload={"max_drawdown_pct": max_dd, "since": kpis.get("max_drawdown_date")},
                    dedupe_key="drawdown_threshold",
                )
            )

        # Rule 4: high-impact bearish news on held tickers
        # Group bearish news by held asset → ONE digest alert per asset per day
        # (avoids spamming one alert per headline). Only fires if >= 2 bearish headlines.
        held_tickers = {p["ticker"] for p in portfolio.get("positions", [])}
        news = await self.news_service.get_news("all", limit=40)
        by_asset: dict[str, list[dict]] = {}
        for item in news:
            if item.get("impact") != "bearish":
                continue
            hits = set(item.get("impactedAssets", [])) & held_tickers
            for ticker in hits:
                by_asset.setdefault(ticker, []).append(item)

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for ticker, items in by_asset.items():
            if len(items) < 2:
                continue  # a single headline isn't a signal — skip the noise
            top = items[:4]
            lines = []
            for it in top:
                src = it.get("source", "")
                title = it.get("title", "")
                url = it.get("url", "")
                lines.append(f"• {src}: {title}" + (f"\n  {url}" if url else ""))
            body = (
                f"{len(items)} titulares bajistas sobre {ticker} hoy:\n\n" + "\n".join(lines)
            )
            created.append(
                await self._maybe_create(
                    kind="news_bearish",
                    severity="warning",
                    title=f"📰 {len(items)} noticias bajistas sobre {ticker}",
                    body=body,
                    payload={"ticker": ticker, "count": len(items),
                             "urls": [it.get("url") for it in top]},
                    dedupe_key=f"news_bearish:{ticker}:{today_str}",  # max 1/asset/day
                )
            )

        return [c for c in created if c is not None]

    async def _maybe_create(
        self,
        *,
        kind: str,
        severity: str,
        title: str,
        body: str,
        payload: dict,
        dedupe_key: str,
    ) -> dict | None:
        """Create an alert if no equivalent one exists within DEDUPE_WINDOW_HOURS."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUPE_WINDOW_HOURS)
        async with session_scope() as session:
            stmt = (
                select(Alert)
                .where(Alert.kind == kind)
                .where(Alert.triggered_at >= cutoff)
            )
            existing_rows = (await session.execute(stmt)).scalars().all()
            for row in existing_rows:
                if (row.payload or {}).get("__dedupe_key") == dedupe_key:
                    return None  # already alerted recently

            payload_with_key = {**payload, "__dedupe_key": dedupe_key}
            alert = Alert(
                kind=kind,
                severity=severity,
                title=title,
                body=body,
                payload=payload_with_key,
                triggered_at=datetime.now(timezone.utc),
            )
            session.add(alert)
            await session.flush()
            alert_id = alert.id

        # Notify with rich HTML
        from app.services.notifications.telegram import html_escape as esc
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "🔔")
        html = (
            f"{severity_emoji} <b>{esc(title)}</b>\n"
            f"<i>{esc(severity.upper())}</i>\n\n"
            f"{esc(body)}"
        )
        delivered = await self.telegram.send_html(html)
        if delivered:
            async with session_scope() as session:
                row = await session.get(Alert, alert_id)
                if row:
                    row.delivered_telegram = True

        return {
            "id": alert_id,
            "kind": kind,
            "severity": severity,
            "title": title,
            "delivered_telegram": delivered,
        }
