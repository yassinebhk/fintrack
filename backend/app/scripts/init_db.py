"""Create all tables. Safe to re-run."""

import asyncio

from loguru import logger

from app.db import init_db
from app.logging_config import setup_logging


async def main() -> None:
    setup_logging()
    await init_db()
    logger.info("✅ database ready")


if __name__ == "__main__":
    asyncio.run(main())
