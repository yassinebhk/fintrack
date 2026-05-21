"""Resolve the configured LLM client with automatic fallback to Groq."""

from app.config import get_settings
from app.llm.base import LLMClient
from app.llm.gemini import GeminiClient
from app.llm.groq import GroqClient


def get_llm_client(prefer: str | None = None) -> LLMClient:
    settings = get_settings()
    choice = prefer or settings.llm_provider

    if choice == "gemini" and settings.has_gemini:
        return GeminiClient()
    if choice == "groq" and settings.has_groq:
        return GroqClient()

    if settings.has_gemini:
        return GeminiClient()
    if settings.has_groq:
        return GroqClient()

    raise RuntimeError("No LLM provider configured (set GEMINI_API_KEY or GROQ_API_KEY)")
