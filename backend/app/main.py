"""FastAPI app factory with lifespan-managed DB init and scheduler stub."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import __version__
from app.api import build_api_router
from app.config import get_settings
from app.db import init_db
from app.logging_config import setup_logging
from app.scheduler import start_scheduler, stop_scheduler


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
