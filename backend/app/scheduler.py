"""APScheduler instance that owns the periodic background jobs.

Each phase adds its own job:
- Fase 1.1: Kraken sync every 15 min
- Fase 2.3: Daily briefing at 08:00 Europe/Madrid
- Fase 2.4: Alerts loop every 5 min
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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


async def _opportunities_prewarm_job() -> None:
    """Generate today's opportunities ahead of time so the morning's first view
    (web or Telegram) is instant instead of waiting ~1-2 min for a cold scan."""
    try:
        from app.services.opportunities import get_opportunity_service

        payload = await get_opportunity_service().generate(force=True)
        logger.info(
            "opportunities pre-warmed: {} ideas over {} instruments",
            len(payload.get("opportunities", [])),
            payload.get("universe_size"),
        )
    except Exception as exc:
        logger.error("opportunities pre-warm failed: {}", exc)


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

        sched.add_job(
            _opportunities_prewarm_job,
            trigger=CronTrigger(hour=7, minute=30, timezone=settings.timezone),
            id="opportunities_prewarm",
            name="Pre-warm daily opportunities at 07:30",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: opportunities_prewarm @ 07:30 {}", settings.timezone)

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
            _alerts_job,
            trigger=IntervalTrigger(minutes=5),
            id="alerts_loop",
            name="Alerts rules engine",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled: alerts_loop every 5 min")


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
