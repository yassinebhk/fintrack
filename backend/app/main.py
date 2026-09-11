"""FastAPI app factory with lifespan-managed DB init and scheduler stub."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.api import build_api_router
from app.config import BACKEND_DIR, get_settings
from app.db import init_db, session_scope
from app.logging_config import setup_logging
from app.scheduler import start_scheduler, stop_scheduler


FRONTEND_DIR = (BACKEND_DIR.parent / "frontend").resolve()


async def _seed_if_empty() -> None:
    """On first boot (e.g. fresh Render container), seed the DB from the legacy CSV.

    This legacy path predates multi-user (Position now requires user_id), so it
    checks the raw table count directly rather than through the user-scoped
    PositionRepository — it only ever matters for a truly empty, brand-new DB.
    """
    from sqlalchemy import func, select

    from app.models.position import Position

    async with session_scope() as session:
        count = (await session.execute(select(func.count(Position.id)))).scalar_one()
    if count > 0:
        logger.info("db already populated ({} positions), skipping legacy seed", count)
        return
    csv_path = BACKEND_DIR / "data" / "positions.csv"
    if not csv_path.exists():
        logger.info("no legacy positions.csv to seed from")
        return
    # Positions now require a user_id (multi-user Fase 1) — on a genuinely empty
    # DB there's no user yet to own them (nobody has logged in), so this legacy
    # CSV auto-seed no longer has a safe target. Just seed the shared ticker
    # mappings table (not per-user) and stop there.
    logger.info("db empty + legacy CSV present, but legacy position auto-seed is "
                "disabled post multi-user — log in first, then import manually")
    try:
        from app.scripts.migrate_legacy import seed_ticker_mappings
        await seed_ticker_mappings()
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

    settings = get_settings()
    # Wildcard origin + credentialed (cookie) requests is invalid per the CORS spec —
    # browsers reject it. Frontend+backend are same-origin in production anyway; this
    # list only really matters for local dev (frontend on a different port).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://fintrack.34-123-238-158.sslip.io",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key or "dev-insecure-change-me",
        same_site="lax",
        https_only=not settings.database_url.startswith("sqlite"),
    )

    app.include_router(build_api_router())

    # Serve the frontend SPA from the same origin as the API.
    # / → frontend/index.html
    # /css/*, /js/*, /pages/* → static files
    # /api/* → backend (handled by routers above)
    if FRONTEND_DIR.exists():
        # Mount asset subdirectories
        for sub in ("css", "js", "pages"):
            d = FRONTEND_DIR / sub
            if d.exists():
                app.mount(f"/{sub}", StaticFiles(directory=str(d)), name=sub)

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(str(FRONTEND_DIR / "index.html"))

        # Optional favicon fallback (legacy frontend doesn't ship one)
        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon() -> FileResponse:
            for candidate in ("favicon.ico", "favicon.png", "logo.png"):
                p = FRONTEND_DIR / candidate
                if p.exists():
                    return FileResponse(str(p))
            return FileResponse(str(FRONTEND_DIR / "index.html"))

        logger.info("frontend mounted from {}", FRONTEND_DIR)
    else:
        logger.warning("frontend dir not found at {} — UI will not be served", FRONTEND_DIR)

    return app


app = create_app()
