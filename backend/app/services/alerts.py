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
PORTFOLIO_MOVE_DOWN_PCT = -3.0     # whole-book down day
PORTFOLIO_MOVE_UP_PCT = 4.0        # whole-book up day (higher bar → less noise)
PORTFOLIO_MOVE_BIG_PCT = 6.0       # |move| above this bumps severity

# Per-asset aggressive intraday move (BOTH directions), by asset class
EQUITY_MOVE_WARN_PCT = 5.0
EQUITY_MOVE_CRIT_PCT = 9.0
CRYPTO_MOVE_WARN_PCT = 9.0         # crypto swings a lot → higher bar to avoid spam
CRYPTO_MOVE_CRIT_PCT = 15.0

DRAWDOWN_THRESHOLD_PCT = -15.0
DEDUPE_WINDOW_HOURS = 24


def _is_crypto(asset_type: str | None, ticker: str) -> bool:
    if (asset_type or "").lower() in ("crypto", "cryptocurrency", "coin"):
        return True
    t = (ticker or "").upper()
    return t.endswith("-USD") or t.endswith("-EUR") or t.endswith("-USDT")


class AlertsEngine:
    _scanner_singleton = None

    def __init__(self) -> None:
        self.portfolio_service = PortfolioService()
        self.news_service = NewsService()
        self.telegram = TelegramNotifier()

    async def evaluate(self) -> list[dict]:
        """Run all rules. Returns a list of alert payloads created."""
        portfolio = await self.portfolio_service.calculate_portfolio()
        created: list[dict] = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Rule 1: whole-portfolio aggressive move (BOTH directions)
        daily_pct = portfolio.get("daily_change_pct", 0) or 0
        if daily_pct <= PORTFOLIO_MOVE_DOWN_PCT or daily_pct >= PORTFOLIO_MOVE_UP_PCT:
            up = daily_pct >= 0
            big = abs(daily_pct) >= PORTFOLIO_MOVE_BIG_PCT
            created.append(
                await self._maybe_create(
                    kind="portfolio_move",
                    severity=("warning" if big else "info") if up else ("critical" if big else "warning"),
                    title=f"{'📈' if up else '📉'} Cartera {'sube' if up else 'cae'} {daily_pct:+.2f}% hoy",
                    body=(
                        f"Tu cartera está en {portfolio.get('total_value', 0):.2f} "
                        f"{portfolio.get('base_currency', 'EUR')} ({daily_pct:+.2f}% hoy)."
                    ),
                    payload={"daily_change_pct": daily_pct, "total_value": portfolio.get("total_value"),
                             "direction": "up" if up else "down"},
                    dedupe_key=f"portfolio_move:{'up' if up else 'down'}:{today_str}",
                )
            )

        # Rule 2: individual holding aggressive intraday move (BOTH directions)
        held_tickers: set[str] = set()
        for pos in portfolio.get("positions", []):
            held_tickers.add(pos.get("ticker"))
            created.append(await self._eval_move(
                ticker=pos.get("ticker"),
                name=pos.get("ticker"),
                asset_type=pos.get("type"),
                broker=pos.get("broker"),
                pct=pos.get("day_change_pct", 0) or 0,
                price=pos.get("current_price") or 0,
                currency=portfolio.get("base_currency", "EUR"),
                weight=pos.get("weight"),
                source="portfolio",
            ))

        # Rule 2b: tickers tracked in plans/watchlist that AREN'T in the synced portfolio
        # (e.g. the tactical ETFs just bought in Trade Republic / MyInvestor). Price via Yahoo.
        for tk, label in (await self._watchlist_extra(held_tickers)).items():
            try:
                price = await self._scanner().yahoo.get_price(tk)
            except Exception as exc:
                logger.debug("alerts watchlist price {} failed: {}", tk, exc)
                continue
            if not price:
                continue
            created.append(await self._eval_move(
                ticker=tk,
                name=label or price.get("name") or tk,
                asset_type="crypto" if _is_crypto(None, tk) else "etf",
                broker=None,
                pct=price.get("change_percent", 0) or 0,
                price=price.get("price") or 0,
                currency=price.get("currency"),
                weight=None,
                source="watchlist",
            ))

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
        news = await self.news_service.get_news("all", limit=40)
        by_asset: dict[str, list[dict]] = {}
        for item in news:
            if item.get("impact") != "bearish":
                continue
            hits = set(item.get("impactedAssets", [])) & held_tickers
            for ticker in hits:
                by_asset.setdefault(ticker, []).append(item)

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

    # ---- helpers -----------------------------------------------------------

    def _scanner(self):
        if AlertsEngine._scanner_singleton is None:
            from app.services.discovery.market_scanner import MarketScanner
            AlertsEngine._scanner_singleton = MarketScanner()
        return AlertsEngine._scanner_singleton

    async def _watchlist_extra(self, held: set[str]) -> dict[str, str]:
        """Plan/watchlist tickers not already in the portfolio. Returns {ticker: label}."""
        out: dict[str, str] = {}
        try:
            from app.services import plans
            data = await plans._load()
            for p in data.get("plans", []):
                for h in p.get("holdings", []):
                    tk = (h.get("ticker") or "").strip()
                    if tk and tk not in held and tk not in out:
                        out[tk] = h.get("label") or tk
        except Exception as exc:
            logger.debug("alerts watchlist load failed: {}", exc)
        return out

    async def _eval_move(self, *, ticker, name, asset_type, broker, pct, price,
                         currency, weight, source) -> dict | None:
        """Emit an alert if |pct| crosses the aggressive-move bar for this asset class."""
        if not ticker:
            return None
        crypto = _is_crypto(asset_type, ticker)
        warn = CRYPTO_MOVE_WARN_PCT if crypto else EQUITY_MOVE_WARN_PCT
        crit = CRYPTO_MOVE_CRIT_PCT if crypto else EQUITY_MOVE_CRIT_PCT
        if abs(pct) < warn:
            return None
        up = pct >= 0
        big = abs(pct) >= crit
        severity = ("warning" if big else "info") if up else ("critical" if big else "warning")
        bits = [str(b) for b in (asset_type, broker) if b]
        ctx = f" ({', '.join(bits)})" if bits else ""
        wtxt = f", peso {weight:.1f}%" if isinstance(weight, (int, float)) else ""
        try:
            ptxt = f"{float(price):.6g} {currency or ''}".strip()
        except Exception:
            ptxt = "-"
        return await self._maybe_create(
            kind="asset_move",
            severity=severity,
            title=f"{'📈' if up else '📉'} {ticker} {'sube' if up else 'cae'} {pct:+.2f}% hoy",
            body=f"{name}{ctx}: {ptxt} ({pct:+.2f}% intradía{wtxt}).",
            payload={"ticker": ticker, "day_change_pct": round(pct, 2),
                     "direction": "up" if up else "down", "source": source},
            dedupe_key=f"asset_move:{ticker}:{'up' if up else 'down'}",
        )

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
