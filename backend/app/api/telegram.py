"""Telegram webhook — receives inbound messages and routes them to the bot handler.

CRITICAL: Telegram retries a webhook update if it doesn't get a 200 within
~a few seconds. Our handler calls the LLM (10-30s) + portfolio (cold start),
so we MUST ack immediately and process in the background, otherwise Telegram
re-delivers the same message many times (causing duplicate replies).
"""

import asyncio

from fastapi import APIRouter, Request
from loguru import logger

from app.config import get_settings
from app.services.telegram_bot import TelegramBotHandler

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

# Dedup recently-seen update_ids (in-memory; resets on restart, which is fine)
_seen_update_ids: set[int] = set()


async def _safe_handle(chat_id: str, text: str) -> None:
    try:
        await TelegramBotHandler().handle(chat_id, text)
    except Exception as exc:
        logger.exception("telegram background handler failed: {}", exc)


@router.post("/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Ack immediately; process the message in the background."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    update_id = update.get("update_id")
    if update_id is not None:
        if update_id in _seen_update_ids:
            return {"ok": True}  # duplicate delivery — ignore
        _seen_update_ids.add(update_id)
        if len(_seen_update_ids) > 1000:
            _seen_update_ids.clear()

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    # Fire-and-forget: respond to Telegram now, do the slow work after.
    asyncio.create_task(_safe_handle(str(chat_id), text))
    return {"ok": True}


@router.get("/webhook-info")
async def webhook_info() -> dict:
    s = get_settings()
    return {
        "bot_configured": bool(s.telegram_bot_token),
        "chat_authorized": bool(s.telegram_chat_id),
    }
