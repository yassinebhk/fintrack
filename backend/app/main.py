"""FastAPI app factory with lifespan-managed DB init and scheduler stub."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import __version__
from app.api import build_api_router
from app.config import BACKEND_DIR, get_settings
from app.db import init_db, session_scope
from app.logging_config import setup_logging
from app.repositories import PositionRepository
from app.scheduler import start_scheduler, stop_scheduler


async def _seed_if_empty() -> None:
    """On first boot (e.g. fresh Render container), seed the DB from the legacy CSV."""
    async with session_scope() as session:
        count = await PositionRepository(session).count()
    if count > 0:
        logger.info("db already populated ({} positions), skipping legacy seed", count)
        return
    csv_path = BACKEND_DIR / "data" / "positions.csv"
    if not csv_path.exists():
        logger.info("no legacy positions.csv to seed from")
        return
    logger.info("db empty + legacy CSV present → running migrate_legacy")
    try:
        from app.scripts.migrate_legacy import (
            migrate_positions,
            migrate_snapshots,
            seed_ticker_mappings,
        )
        await seed_ticker_mappings()
        await migrate_positions(csv_path)
        snaps_path = BACKEND_DIR / "data" / "historical_values.json"
        if snaps_path.exists():
            await migrate_snapshots(snaps_path)
        logger.info("seed complete")
    except Exception as exc:
        logger.error("seed failed: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("FinTrack v{} starting", __version__)
    logger.info("LLM provider: {}, base_currency: {}", settings.llm_provider, settings.base_currency)
    logger.info(
        "integrations: gemini={}, kraken={}, telegram={}, groq={}",
        settings.has_gemini,
        settings.has_kraken,
        settings.has_telegram,
        settings.has_groq,
    )

    await init_db()
    logger.info("database ready at {}", settings.database_url)

    await _seed_if_empty()

    start_scheduler()

    yield
    await stop_scheduler()
    logger.info("FinTrack shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="FinTrack API",
        description="Personal finance dashboard with autonomous AI assistant",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(build_api_router())
    return app


app = create_app()
