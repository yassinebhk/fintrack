"""Systematic engine endpoints — paper portfolio (no real money), scoped to the
logged-in user. Heavy steps run in the background to avoid a gateway timeout."""

import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.auth import get_current_user
from app.models.user import User

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
async def paper_report(current_user: User = Depends(get_current_user)) -> dict:
    from app.services.systematic import paper
    return await paper.report(current_user.id)


@router.post("/paper/rebalance")
async def paper_rebalance(current_user: User = Depends(get_current_user)) -> dict:
    from app.services.systematic import paper

    async def _job(user_id: int):
        try:
            await paper.rebalance(user_id)
            await paper.mark(user_id)
        except Exception:
            logger.exception("systematic rebalance failed")
    asyncio.create_task(_job(current_user.id))
    return {"status": "accepted"}


@router.post("/paper/mark")
async def paper_mark(current_user: User = Depends(get_current_user)) -> dict:
    from app.services.systematic import paper
    asyncio.create_task(paper.mark(current_user.id))
    return {"status": "accepted"}


@router.post("/paper/reset")
async def paper_reset(current_user: User = Depends(get_current_user)) -> dict:
    from app.services.systematic import paper
    return await paper.reset(current_user.id)


@router.post("/digest")
async def digest(secret: str = "") -> dict:
    """Owner-only admin/cron trigger (Telegram stays owner-only until Fase 2)."""
    _gate(secret)

    async def _send():
        from app.auth import get_owner_user_id_cached
        from app.services.systematic.digest import telegram_digest
        from app.services.notifications.telegram import TelegramNotifier
        try:
            owner_id = await get_owner_user_id_cached()
            if owner_id is None:
                return
            await TelegramNotifier().send_html(await telegram_digest(owner_id))
        except Exception:
            logger.exception("systematic digest failed")
    asyncio.create_task(_send())
    return {"status": "accepted"}
