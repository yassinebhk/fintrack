"""Telegram bot notifier (no python-telegram-bot dependency — direct API).

Telegram supports two formatting modes: MarkdownV2 (very strict, easy to break)
and HTML (lenient, predictable). We always send HTML — it lets us use
<b>, <i>, <code>, <pre>, <a> and only requires escaping &, <, >.
"""

import httpx
from loguru import logger

from app.config import get_settings


TG_MAX_LEN = 4000  # leave headroom under Telegram's 4096 limit


def html_escape(text: str) -> str:
    """Escape Telegram-HTML-reserved chars (only &, <, >)."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


class TelegramNotifier:
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self) -> None:
        settings = get_settings()
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)

    async def _post(self, body: dict) -> bool:
        if not self.enabled:
            logger.debug("telegram disabled (no token/chat_id)")
            return False
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.BASE_URL.format(token=self.token, method="sendMessage"),
                    json=body,
                )
                if resp.status_code >= 400:
                    logger.warning("telegram send failed ({}): {}", resp.status_code, resp.text[:200])
                    return False
            return True
        except Exception as exc:
            logger.error("telegram POST failed: {}", exc)
            return False

    async def send_text(self, text: str) -> bool:
        """Send plain text (no formatting)."""
        return await self._post({
            "chat_id": self.chat_id,
            "text": text[:TG_MAX_LEN],
            "disable_web_page_preview": True,
        })

    async def send_html(self, html: str) -> bool:
        """Send HTML-formatted message. Safe; falls back to plain if HTML is rejected."""
        ok = await self._post({
            "chat_id": self.chat_id,
            "text": html[:TG_MAX_LEN],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        if ok:
            return True
        # Strip tags and retry as plain
        import re
        plain = re.sub(r"<[^>]+>", "", html)
        plain = plain.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return await self.send_text(plain)

    async def send_photo(self, photo_url: str, caption: str = "") -> bool:
        """Send a photo by URL (e.g. a QuickChart image). caption supports HTML."""
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.BASE_URL.format(token=self.token, method="sendPhoto"),
                    json={
                        "chat_id": self.chat_id,
                        "photo": photo_url,
                        "caption": caption[:1000],
                        "parse_mode": "HTML",
                    },
                )
                if resp.status_code >= 400:
                    logger.warning("telegram sendPhoto failed ({}): {}", resp.status_code, resp.text[:150])
                    return False
            return True
        except Exception as exc:
            logger.error("telegram send_photo failed: {}", exc)
            return False

    # Kept for backward compat — new code should call send_html
    async def send_markdown_v2(self, text: str) -> bool:
        return await self.send_html(text)
