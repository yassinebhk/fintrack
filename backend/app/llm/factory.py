"""Resolve the configured LLM client with real runtime fallback.

When both Gemini and Groq are configured, callers get a FallbackLLMClient
that tries the primary provider and transparently falls back to the
secondary on quota/availability errors (429 / RESOURCE_EXHAUSTED / 5xx).
"""

from loguru import logger

from app.config import get_settings
from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.llm.gemini import GeminiClient
from app.llm.groq import GroqClient


_FALLBACK_TRIGGERS = ("429", "resource_exhausted", "quota", "503", "unavailable", "500")


def _should_fallback(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in _FALLBACK_TRIGGERS)


class FallbackLLMClient:
    """Tries `primary`, falls back to `secondary` on quota/availability errors."""

    def __init__(self, primary: LLMClient, secondary: LLMClient, primary_name: str, secondary_name: str) -> None:
        self.primary = primary
        self.secondary = secondary
        self.primary_name = primary_name
        self.secondary_name = secondary_name

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        try:
            return await self.primary.generate(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )
        except Exception as exc:
            if not _should_fallback(exc):
                raise
            logger.warning(
                "{} failed ({}); falling back to {}",
                self.primary_name,
                str(exc)[:80],
                self.secondary_name,
            )
            # secondary picks its own default model (don't pass Gemini model name to Groq)
            return await self.secondary.generate(
                messages,
                model=None,
                temperature=temperature,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )


def get_llm_client(prefer: str | None = None) -> LLMClient:
    settings = get_settings()
    choice = prefer or settings.llm_provider

    gemini = GeminiClient() if settings.has_gemini else None
    groq = GroqClient() if settings.has_groq else None

    # Both available → wrap with runtime fallback (primary chosen by config)
    if gemini and groq:
        if choice == "groq":
            return FallbackLLMClient(groq, gemini, "groq", "gemini")
        return FallbackLLMClient(gemini, groq, "gemini", "groq")

    if choice == "groq" and groq:
        return groq
    if choice == "gemini" and gemini:
        return gemini
    if gemini:
        return gemini
    if groq:
        return groq

    raise RuntimeError("No LLM provider configured (set GEMINI_API_KEY or GROQ_API_KEY)")
