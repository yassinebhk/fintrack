"""Telegram webhook — receives inbound messages and routes them to the bot handler."""

from fastapi import APIRouter, Request
from loguru import logger

from app.config import get_settings
from app.services.telegram_bot import TelegramBotHandler

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Telegram calls this on every new message (set via setWebhook)."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}  # ack anything to avoid Telegram retry storms

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    try:
        await TelegramBotHandler().handle(str(chat_id), text)
    except Exception as exc:
        logger.exception("telegram webhook handler failed: {}", exc)

    return {"ok": True}


@router.get("/webhook-info")
async def webhook_info() -> dict:
    """Diagnostic: report whether the bot is configured."""
    s = get_settings()
    return {
        "bot_configured": bool(s.telegram_bot_token),
        "chat_authorized": bool(s.telegram_chat_id),
    }
