"""Send + pin the daily portfolio summary talking directly to the DB, with no
dependency on the web service being up. Stopgap for when Render is suspended
(GitHub Actions' own daily-summary.yml wakes/hits the Render URL, which is a
no-op while it's suspended) — this workflow reaches the DB straight from a
GitHub-hosted runner instead. Idempotent per day unless FORCE_SEND=1."""
import asyncio
import os

from loguru import logger

from app.logging_config import setup_logging
from app.services.portfolio_report import send_daily_summary_pinned


async def main() -> None:
    setup_logging()
    force = os.getenv("FORCE_SEND") == "1"
    res = await send_daily_summary_pinned(force=force)
    logger.info("daily summary direct-send: {}", res)


if __name__ == "__main__":
    asyncio.run(main())
