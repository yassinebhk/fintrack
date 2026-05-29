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
from app.llm.openai_compat import OpenAICompatClient


class ChainLLMClient:
    """Tries each provider in order; on ANY failure moves to the next. All are free,
    so we exhaust the whole chain before giving up. The 'model' arg is ignored for
    secondaries — each provider uses its own default model."""

    def __init__(self, providers: list[tuple[str, LLMClient]]) -> None:
        # providers: list of (name, client) in priority order
        self.providers = providers

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        errors = []
        for i, (name, client) in enumerate(self.providers):
            try:
                # Only the first (primary) honors a caller-passed model name.
                return await client.generate(
                    messages,
                    model=model if i == 0 else None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_schema=json_schema,
                )
            except Exception as exc:
                errors.append(f"{name}: {str(exc)[:200]}")
                logger.warning("LLM provider {} failed ({}); trying next", name, str(exc)[:150])
        raise RuntimeError("all LLM providers failed — " + " || ".join(errors))


def get_llm_client(prefer: str | None = None) -> LLMClient:
    settings = get_settings()
    choice = prefer or settings.llm_provider

    # Build the provider chain from whatever keys are configured. Order: the
    # configured primary first, then the rest as free fallbacks.
    available: dict[str, LLMClient] = {}
    if settings.has_gemini:
        available["gemini"] = GeminiClient()
    if settings.has_groq:
        available["groq"] = GroqClient()
    if settings.openrouter_api_key:
        available["openrouter"] = OpenAICompatClient(
            base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key,
            model=settings.openrouter_model, name="openrouter",
        )
    if settings.cerebras_api_key:
        available["cerebras"] = OpenAICompatClient(
            base_url="https://api.cerebras.ai/v1", api_key=settings.cerebras_api_key,
            model=settings.cerebras_model, name="cerebras",
        )

    if not available:
        raise RuntimeError("No LLM provider configured (set GEMINI_API_KEY / GROQ_API_KEY / ...)")

    # Priority: configured choice first, then a sensible free order. Cerebras
    # (generous free tier) before OpenRouter (whose free models are heavily limited).
    order = [choice, "gemini", "groq", "cerebras", "openrouter"]
    seen, chain = set(), []
    for name in order:
        if name in available and name not in seen:
            seen.add(name)
            chain.append((name, available[name]))

    if len(chain) == 1:
        return chain[0][1]
    return ChainLLMClient(chain)
