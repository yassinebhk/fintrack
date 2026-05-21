"""Telegram bot notifier (no python-telegram-bot dependency — direct API)."""

import httpx
from loguru import logger

from app.config import get_settings


class TelegramNotifier:
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self) -> None:
        settings = get_settings()
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)

    async def send_text(self, text: str) -> bool:
        if not self.enabled:
            logger.debug("telegram disabled (no token/chat_id)")
            return False
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.BASE_URL.format(token=self.token, method="sendMessage"),
                    json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                )
                resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("telegram send_text failed: {}", exc)
            return False

    async def send_markdown_v2(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.BASE_URL.format(token=self.token, method="sendMessage"),
                    json={
                        "chat_id": self.chat_id,
                        "text": text[:4000],
                        "parse_mode": "MarkdownV2",
                        "disable_web_page_preview": True,
                    },
                )
                if resp.status_code >= 400:
                    logger.warning("telegram markdown failed ({}), falling back to plain", resp.status_code)
                    # Fallback: strip backslashes the escape inserted, send plain
                    plain = text.replace("\\", "")
                    return await self.send_text(plain)
            return True
        except Exception as exc:
            logger.error("telegram send_markdown_v2 failed: {}", exc)
            return False
