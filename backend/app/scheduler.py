"""APScheduler instance that owns the periodic background jobs.

Each phase adds its own job:
- Fase 1.1: Kraken sync every 15 min
- Fase 2.3: Daily briefing at 08:00 Europe/Madrid
- Fase 2.4: Alerts loop every 5 min
"""

from datetime import datetime
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
    # 1) Daily portfolio snapshot summary (live values per position, like checking each app)
    try:
        from app.services.telegram_bot import TelegramBotHandler

        await TelegramBotHandler()._send_quick_summary()
        logger.info("daily portfolio summary sent")
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


async def _creators_job() -> None:
    """Check curated YouTube finance channels for new videos every few hours."""
    try:
        from app.services.creators import CreatorsService

        result = await CreatorsService().check_and_process(deliver=True)
        logger.info("creators job: {} new videos processed", result.get("new_videos", 0))
    except Exception as exc:
        logger.error("creators job failed: {}", exc)


async def _alerts_job() -> None:
    try:
        created = await AlertsEngine().evaluate()
        if created:
            logger.info("alerts: {} new ({} delivered)", len(created), sum(1 for c in created if c.get("delivered_telegram")))
    except Exception as exc:
        logger.error("scheduled alerts evaluation failed: {}", exc)


async def _polymarket_lab_job() -> None:
    """Daily: log fresh model-vs-market paper bets + resolve matured ones. No real money."""
    try:
        from app.services.polymarket import lab
        logged = await lab.log_paper_bets()
        resolved = await lab.evaluate()
        logger.info("polymarket lab: {} new bets, {} resolved", logged.get("new_bets"), resolved.get("resolved_now"))
    except Exception as exc:
        logger.error("polymarket lab job failed: {}", exc)


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
