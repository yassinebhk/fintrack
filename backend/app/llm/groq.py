"""Groq client (Llama 3.3 70B) — fallback when Gemini quota is exhausted."""

import json

import httpx
from loguru import logger

from app.config import get_settings
from app.llm.base import LLMMessage, LLMResponse


class GroqClient:
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.groq_api_key
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY missing")
        self.default_model = "llama-3.3-70b-versatile"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        model = model or self.default_model
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_schema is not None:
            body["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("groq call failed: {}", exc)
            raise

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        structured = None
        if json_schema is not None:
            try:
                structured = json.loads(text)
            except json.JSONDecodeError:
                pass

        return LLMResponse(
            text=text,
            model=model,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            structured=structured,
        )
