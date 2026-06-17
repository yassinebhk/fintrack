"""Systematic engine endpoints — paper portfolio (no real money). Heavy steps run
in the background to avoid the Render gateway timeout."""

import asyncio
import os

from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter(prefix="/api/systematic", tags=["systematic"])
_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


def _gate(secret: str) -> None:
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")


@router.get("/buyable")
async def buyable() -> dict:
    from app.services.systematic.buyable import BUYABLE
    return {"count": len(BUYABLE),
            "universe": [{"ticker": t, "name": n, "asset_class": c} for t, n, c in BUYABLE]}


@router.get("/paper/report")
async def paper_report() -> dict:
    from app.services.systematic import paper
    return await paper.report()


@router.post("/paper/rebalance")
async def paper_rebalance(secret: str = "") -> dict:
    _gate(secret)
    from app.services.systematic import paper

    async def _job():
        try:
            await paper.rebalance()
            await paper.mark()
        except Exception:
            logger.exception("systematic rebalance failed")
    asyncio.create_task(_job())
    return {"status": "accepted"}


@router.post("/paper/mark")
async def paper_mark(secret: str = "") -> dict:
    _gate(secret)
    from app.services.systematic import paper
    asyncio.create_task(paper.mark())
    return {"status": "accepted"}


@router.post("/paper/reset")
async def paper_reset(secret: str = "") -> dict:
    _gate(secret)
    from app.services.systematic import paper
    return await paper.reset()


@router.post("/digest")
async def digest(secret: str = "") -> dict:
    _gate(secret)

    async def _send():
        from app.services.systematic.digest import telegram_digest
        from app.services.notifications.telegram import TelegramNotifier
        try:
            await TelegramNotifier().send_html(await telegram_digest())
        except Exception:
            logger.exception("systematic digest failed")
    asyncio.create_task(_send())
    return {"status": "accepted"}
