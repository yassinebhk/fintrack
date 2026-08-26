"""APScheduler instance that owns the periodic background jobs.

Each phase adds its own job:
- Fase 1.1: Kraken sync every 15 min
- Fase 2.3: Daily briefing at 08:00 Europe/Madrid
- Fase 2.4: Alerts loop every 5 min
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config import get_settings
from app.db import session_scope
from app.services.alerts import AlertsEngine
from app.services.briefing import BriefingService
from app.services.brokers import KrakenService

_scheduler: AsyncIOScheduler | None = None


async def _kraken_sync_job() -> None:
    settings = get_settings()
    if not settings.has_kraken:
        return
    try:
        svc = KrakenService()
        async with session_scope() as session:
            result = await svc.sync_all(session)
        logger.info(
            "scheduled kraken sync: balances={} trades={}",
            result["balances"]["updated"],
            result["trades"]["trades_imported"],
        )
    except Exception as exc:
        logger.error("scheduled kraken sync failed: {}", exc)


async def _briefing_job() -> None:
    # 1) Daily portfolio snapshot summary — sent AND pinned (unpins yesterday's).
    try:
        from app.services.portfolio_report import send_daily_summary_pinned

        res = await send_daily_summary_pinned()
        logger.info("daily portfolio summary sent (pinned={})", res.get("pinned"))
    except Exception as exc:
        logger.error("daily portfolio summary failed: {}", exc)

    # 2) AI briefing (analysis)
    try:
        result = await BriefingService().generate_today(force=True)
        logger.info(
            "scheduled briefing produced: model={} tokens_in={} tokens_out={} delivered={}",
            result.get("model"),
            result.get("tokens_in"),
            result.get("tokens_out"),
            result.get("delivered_telegram"),
        )
    except Exception as exc:
        logger.error("scheduled briefing failed: {}", exc)


async def _scorecard_job() -> None:
    """Evaluate matured recommendations (1m/3m/6m forward returns) once a day."""
    try:
        from app.services.scorecard import evaluate_due

        n = await evaluate_due()
        logger.info("scorecard eval: {} horizon points filled", n)
    except Exception as exc:
        logger.error("scorecard eval failed: {}", exc)


_POSITION_NEWS_TICKERS = ["BTC", "PLTR", "SPCX"]
_POSITION_NEWS_KEY = "position_news_seen_urls"


async def _position_news_job() -> None:
    """Every few hours: check RSS news for the user's 'story-driven' individual
    positions (BTC/PLTR/SPCX — the ones that move on single headlines, unlike
    the diversified ETFs) and Telegram-alert only genuinely NEW articles.
    Not a trading signal (the market has already moved by the time any RSS
    feed carries the story) — purely so the user isn't blindsided."""
    try:
        from sqlalchemy import select
        from app.db import session_scope, upsert_insert
        from app.models import JsonCache
        from app.services.news import NewsService
        from app.services.notifications.telegram import TelegramNotifier

        async with session_scope() as s:
            row = (await s.execute(select(JsonCache).where(JsonCache.key == _POSITION_NEWS_KEY))).scalar_one_or_none()
        seen: set[str] = set((row.payload or {}).get("urls", [])) if row and row.payload else set()

        svc = NewsService()
        new_items = []
        for ticker in _POSITION_NEWS_TICKERS:
            for item in await svc.get_news_for_asset(ticker, limit=5):
                if item.get("url") and item["url"] not in seen:
                    new_items.append((ticker, item))

        if not new_items:
            logger.debug("position news: nothing new")
            return

        emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}
        lines = ["📰 <b>Noticias sobre tus posiciones</b>"]
        for ticker, item in new_items:
            em = emoji.get(item.get("impact", "neutral"), "⚪")
            title = (item.get("title") or "")[:140]
            url, src = item.get("url", ""), item.get("source", "")
            lines.append(f"{em} <b>{ticker}</b>: <a href=\"{url}\">{title}</a> <i>({src})</i>" if url
                         else f"{em} <b>{ticker}</b>: {title} <i>({src})</i>")
        lines.append("\n<i>Contexto, no señal de compra — el precio ya se movió antes de que esto se publicara.</i>")
        await TelegramNotifier().send_html("\n".join(lines))

        seen.update(item["url"] for _, item in new_items)
        payload = {"urls": list(seen)[-200:]}
        from datetime import datetime, timezone
        stmt = upsert_insert()(JsonCache).values(key=_POSITION_NEWS_KEY, payload=payload, updated_at=datetime.now(timezone.utc)) \
            .on_conflict_do_update(index_elements=["key"], set_={"payload": payload, "updated_at": datetime.now(timezone.utc)})
        async with session_scope() as s:
            await s.execute(stmt)
        logger.info("position news: {} new item(s) alerted", len(new_items))
    except Exception as exc:
        logger.error("position news job failed: {}", exc)


async def _creators_job() -> None:
    """Check curated YouTube finance channels for new videos every few hours."""
    try:
        from app.services.creators import CreatorsService

        result = await CreatorsService().check_and_process(deliver=True)
        logger.info("creators job: {} new videos processed", result.get("new_videos", 0))
    except Exception as exc:
        logger.error("creators job failed: {}", exc)


async def _keepalive_job() -> None:
    """Ping our OWN public URL so Render's free tier keeps the dyno awake.

    Render's free web service sleeps after ~15 min without an INBOUND HTTP request.
    Internal APScheduler jobs do NOT reset that idle timer, so cron jobs would never
    fire on a slept dyno. Pinging our public URL every 10 min arrives as inbound
    traffic and keeps the box awake, so all cron jobs fire reliably.

    Only runs 06:00-23:00 (settings.timezone): staying awake 24/7 burns through
    Render's free 750h/month quota mid-cycle and gets the whole service suspended
    (happened 2026-07-25). Letting the dyno sleep overnight keeps monthly usage
    around ~510h, covering every scheduled job (earliest 06:30, latest 22:30).
    No-ops in local/dev where RENDER_EXTERNAL_URL isn't set."""
    import os

    settings = get_settings()
    now = datetime.now(tz=ZoneInfo(settings.timezone))
    if not (6 <= now.hour < 23):
        return

    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        url = f"https://{host}" if host else None
    if not url:
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(f"{url.rstrip('/')}/api/health")
        logger.debug("keepalive self-ping -> {}", r.status_code)
    except Exception as exc:  # never let a transient ping error crash the scheduler
        logger.debug("keepalive self-ping failed: {}", exc)


async def _alerts_job() -> None:
    try:
        created = await AlertsEngine().evaluate()
        if created:
            logger.info("alerts: {} new ({} delivered)", len(created), sum(1 for c in created if c.get("delivered_telegram")))
    except Exception as exc:
        logger.error("scheduled alerts evaluation failed: {}", exc)


async def _monthly_fidelity_contribution_job() -> None:
    """Day 27 of every month: register the user's recurring 100EUR contribution
    to Fidelity MSCI World (IE00BYX5NX33 @ MyInvestor) — same math as
    POST /api/positions/movement (action=aportar): shares bought at that day's
    live price, weighted-average cost updated, buy transaction recorded.

    Idempotent per calendar month: MyInvestor's actual execution date has
    drifted by a day before (e.g. Aug 2026 landed on the 26th, not the 27th,
    for a slightly different amount — a manual entry covered that occurrence),
    so this guards against ever recording a second contribution for a month
    that's already covered, regardless of which day it lands on."""
    ticker, broker, eur_amount = "IE00BYX5NX33", "MyInvestor", 100.0
    try:
        from app.repositories import PositionRepository, TransactionRepository
        from app.services.market import YahooFinanceService
        from app.services.notifications.telegram import TelegramNotifier

        async with session_scope() as session:
            repo = PositionRepository(session)
            existing = await repo.get(ticker, broker)
            if existing is None:
                logger.error("monthly contribution: position {} @ {} not found", ticker, broker)
                return

            now = datetime.now(timezone.utc)
            this_month_txs = await TransactionRepository(session).list_for_ticker(ticker, broker=broker)
            already_done = any(
                t.type == "buy" and t.executed_at.year == now.year and t.executed_at.month == now.month
                for t in this_month_txs
            )
            if already_done:
                logger.info("monthly contribution: {} already has a buy this month, skipping", ticker)
                return

            price_info = await YahooFinanceService().get_price(ticker)
            price = price_info.get("price") if price_info else None
            if not price or price <= 0:
                logger.error("monthly contribution: no price for {}", ticker)
                return

            shares_added = eur_amount / price
            old_cost = existing.quantity * existing.avg_price
            existing.quantity += shares_added
            existing.avg_price = (old_cost + eur_amount) / existing.quantity
            new_qty, new_avg = existing.quantity, existing.avg_price

            await TransactionRepository(session).add(
                type="buy", ticker=ticker, quantity=shares_added, price=price,
                currency="EUR", broker=broker, executed_at=datetime.now(timezone.utc),
                notes=f"Aportación mensual {eur_amount:.2f}€ (recurrente día 27, automática)",
            )
            await session.flush()

        logger.info(
            "monthly contribution: +{:.2f}€ -> {} shares={:.6f} qty={:.6f} avg={:.4f}",
            eur_amount, ticker, shares_added, new_qty, new_avg,
        )
        await TelegramNotifier().send_html(
            f"💰 <b>Aportación mensual registrada</b>\n"
            f"Fidelity MSCI World: +{eur_amount:.0f}€ @ {price:.4f}€ "
            f"({shares_added:.4f} part.)\nTotal: {new_qty:.4f} part. · coste medio {new_avg:.4f}€"
        )
    except Exception as exc:
        logger.error("monthly contribution job failed: {}", exc)


async def _polymarket_lab_job() -> None:
    """Daily: log fresh model-vs-market paper bets + resolve matured ones. No real money.
    Sends the Telegram digest ONLY when something changed (avoids '0 resolved' spam)."""
    try:
        from app.services.polymarket import lab
        logged = await lab.log_paper_bets()
        resolved = await lab.evaluate()
        if (logged.get("new_bets") or 0) > 0 or (resolved.get("resolved_now") or 0) > 0:
            from app.services.notifications.telegram import TelegramNotifier
            await TelegramNotifier().send_html(await lab.telegram_digest())
        logger.info("polymarket lab: {} new, {} resolved", logged.get("new_bets"), resolved.get("resolved_now"))
    except Exception as exc:
        logger.error("polymarket lab job failed: {}", exc)


async def _systematic_rebalance_job() -> None:
    """Weekly: rebalance the systematic paper portfolio, mark it, send the digest."""
    try:
        from app.services.systematic import paper
        from app.services.systematic.digest import telegram_digest
        from app.services.notifications.telegram import TelegramNotifier
        await paper.rebalance()
        await paper.mark()
        await TelegramNotifier().send_html(await telegram_digest())
        logger.info("systematic: weekly rebalance + digest done")
    except Exception as exc:
        logger.error("systematic rebalance job failed: {}", exc)


async def _systematic_mark_job() -> None:
    """Daily: mark the systematic paper portfolio to market (build the NAV curve)."""
    try:
        from app.services.systematic import paper
        res = await paper.mark()
        logger.info("systematic daily mark: {}", res)
    except Exception as exc:
        logger.error("systematic mark job failed: {}", exc)


async def _ipo_spacex_reminder() -> None:
    """One-off heads-up around the SpaceX IPO (12-Jun-2026): how the user's space
    ETF (JEDI) is moving, plus a 'sell the news' caution. Fires on 11 and 12 Jun."""
    try:
        from app.services.discovery.market_scanner import MarketScanner
        from app.services.notifications.telegram import TelegramNotifier
        scanner = MarketScanner()
        price = await scanner.yahoo.get_price("JEDI.DE")
        line = ""
        if price:
            chg = price.get("change_percent", 0) or 0
            line = (f"\nTu <b>Espacio (JEDI)</b>: {price.get('price'):.2f} "
                    f"{price.get('currency','')} ({chg:+.2f}% hoy).")
        html = (
            "🚀 <b>IPO de SpaceX (SPCX) inminente</b> — debut Nasdaq ~12 jun.\n"
            f"{line}\n\n"
            "Recuerda: JEDI <b>no</b> contiene SpaceX (era privada). Un mega-IPO puede "
            "<i>aspirar</i> capital del resto del sector y suele haber <b>'buy the rumor, "
            "sell the news'</b>. Vigila el movimiento; no persigas el día del estreno."
        )
        await TelegramNotifier().send_html(html)
        logger.info("spacex ipo reminder sent")
    except Exception as exc:
        logger.error("spacex ipo reminder failed: {}", exc)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler(timezone=settings.timezone)
    return _scheduler


def setup_jobs() -> None:
    settings = get_settings()
    sched = get_scheduler()

    # Keep-alive self-ping (Render free tier) — must run unconditionally and first,
    # because every other scheduled job depends on the dyno being awake.
    sched.add_job(
        _keepalive_job,
        trigger=IntervalTrigger(minutes=10),
        id="keepalive_self_ping",
        name="Keep Render dyno awake (self-ping /api/health)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("scheduled: keepalive_self_ping every 10 min")

    if settings.has_kraken:
        sched.add_job(
            _kraken_sync_job,
            trigger=IntervalTrigger(minutes=15),
            id="kraken_sync",
            name="Kraken read-only sync",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: kraken_sync every 15 min")

    if settings.has_gemini or settings.has_groq:
        sched.add_job(
            _briefing_job,
            trigger=CronTrigger(hour=8, minute=0, timezone=settings.timezone),
            id="daily_briefing",
            name="Daily AI briefing at 08:00",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: daily_briefing @ 08:00 {}", settings.timezone)

        # NOTE: the heavy opportunities scan is now done off-box by the GitHub-Actions
        # worker (opportunities-scan.yml) → /api/opportunities/ingest-scan, because it
        # OOMs Render's 512MB free tier. So we no longer pre-warm it here.

        sched.add_job(
            _creators_job,
            trigger=IntervalTrigger(hours=4),
            id="creators_check",
            name="Check curated YouTube creators every 4h",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: creators_check every 4h")

        sched.add_job(
            _scorecard_job,
            trigger=CronTrigger(hour=6, minute=30, timezone=settings.timezone),
            id="scorecard_eval",
            name="Evaluate matured recommendations at 06:30",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: scorecard_eval @ 06:30 {}", settings.timezone)

        sched.add_job(
            _alerts_job,
            trigger=IntervalTrigger(minutes=5),
            id="alerts_loop",
            name="Alerts rules engine",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: alerts_loop every 5 min")

        # One-off SpaceX-IPO heads-up (11 & 12 Jun 2026, 09:00). Only schedule
        # future dates so a restart after the event doesn't re-fire them.
        tz = ZoneInfo(settings.timezone)
        now = datetime.now(tz=tz)
        for day in ("2026-06-11", "2026-06-12"):
            run_dt = datetime.fromisoformat(f"{day}T09:00:00").replace(tzinfo=tz)
            if run_dt <= now:
                continue
            sched.add_job(
                _ipo_spacex_reminder,
                trigger=DateTrigger(run_date=run_dt, timezone=settings.timezone),
                id=f"ipo_spacex_{day}",
                name=f"SpaceX IPO heads-up {day}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
        logger.info("scheduled: SpaceX IPO heads-up 11-12 Jun")

    # Recurring monthly contribution — needs no LLM/broker, runs unconditionally.
    sched.add_job(
        _monthly_fidelity_contribution_job,
        trigger=CronTrigger(day=27, hour=9, minute=0, timezone=settings.timezone),
        id="monthly_fidelity_contribution",
        name="Monthly 100EUR contribution to Fidelity MSCI World (day 27)",
        replace_existing=True, max_instances=1, coalesce=True,
    )
    logger.info("scheduled: monthly_fidelity_contribution @ day 27 09:00 {}", settings.timezone)

    # Position news watch (BTC/PLTR/SPCX) — needs no LLM/broker, runs unconditionally.
    sched.add_job(
        _position_news_job,
        trigger=IntervalTrigger(hours=6),
        id="position_news",
        name="Watch news for BTC/PLTR/SPCX, alert only on new items",
        replace_existing=True, max_instances=1, coalesce=True,
    )
    logger.info("scheduled: position_news every 6h")

    # Polymarket paper-trading lab — needs no LLM/broker, so it runs unconditionally.
    sched.add_job(
        _polymarket_lab_job,
        trigger=CronTrigger(hour=7, minute=15, timezone=settings.timezone),
        id="polymarket_lab",
        name="Polymarket paper-trading lab (log edges + resolve) daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("scheduled: polymarket_lab @ 07:15 {}", settings.timezone)

    # Systematic paper portfolio (multi-asset) — additive, no broker/LLM needed.
    sched.add_job(
        _systematic_rebalance_job,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=settings.timezone),
        id="systematic_rebalance",
        name="Systematic paper portfolio weekly rebalance + digest",
        replace_existing=True, max_instances=1, coalesce=True,
    )
    sched.add_job(
        _systematic_mark_job,
        trigger=CronTrigger(hour=22, minute=30, timezone=settings.timezone),
        id="systematic_mark",
        name="Systematic paper portfolio daily NAV mark",
        replace_existing=True, max_instances=1, coalesce=True,
    )
    logger.info("scheduled: systematic rebalance (Mon 07:30) + daily mark (22:30) {}", settings.timezone)


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        setup_jobs()
        sched.start()
        logger.info("scheduler started ({} job(s))", len(sched.get_jobs()))


async def stop_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        logger.info("scheduler stopped")
