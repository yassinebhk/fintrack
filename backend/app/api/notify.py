"""Secret-gated endpoint to push an arbitrary HTML message to the configured Telegram chat."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/notify", tags=["notify"])
_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


class NotifyIn(BaseModel):
    html: str = Field(min_length=1)


@router.post("/send")
async def send(payload: NotifyIn, secret: str = "") -> dict:
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    try:
        from app.services.notifications.telegram import TelegramNotifier
        ok = await TelegramNotifier().send_html(payload.html[:4000])
        return {"sent": bool(ok)}
    except Exception as exc:
        logger.exception("notify send failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
