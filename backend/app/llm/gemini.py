"""Google Gemini client using google-genai SDK.

Tier defaults:
- orchestrator -> gemini-2.5-pro
- agent        -> gemini-2.5-flash
- cheap        -> gemini-2.5-flash-lite
"""

import asyncio
import json

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from loguru import logger

from app.config import get_settings
from app.llm.base import LLMMessage, LLMResponse


class GeminiClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY missing")
        self._client = genai.Client(api_key=self.api_key)
        self.default_model = settings.gemini_model_agent
        self.fallback_model = settings.gemini_model_fallback

    def _to_contents(self, messages: list[LLMMessage]) -> tuple[str | None, list[dict]]:
        """Split messages into (system_instruction, contents)."""
        system_parts: list[str] = []
        contents: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return ("\n\n".join(system_parts) if system_parts else None, contents)

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
        system_instruction, contents = self._to_contents(messages)

        config_kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if json_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = json_schema

        attempted_models = [model]
        if model != self.fallback_model:
            attempted_models.append(self.fallback_model)

        last_exc: Exception | None = None
        response = None
        for candidate in attempted_models:
            backoff = 2.0
            for attempt in range(4):
                try:
                    response = await self._client.aio.models.generate_content(
                        model=candidate,
                        contents=contents,
                        config=genai_types.GenerateContentConfig(**config_kwargs),
                    )
                    model = candidate
                    last_exc = None
                    break
                except genai_errors.ClientError as exc:
                    msg = str(exc)
                    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                        logger.warning("gemini 429 on {} (attempt {}); trying fallback", candidate, attempt + 1)
                        last_exc = exc
                        break  # client error → switch model
                    logger.error("gemini client error on {}: {}", candidate, exc)
                    last_exc = exc
                    break
                except genai_errors.ServerError as exc:
                    msg = str(exc)
                    logger.warning("gemini server 5xx on {} (attempt {}): {}", candidate, attempt + 1, msg[:120])
                    last_exc = exc
                    if attempt < 3:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    break
                except Exception as exc:
                    logger.error("gemini call failed on {}: {}", candidate, exc)
                    last_exc = exc
                    break
            if response is not None:
                break

        if response is None:
            raise last_exc if last_exc else RuntimeError("Gemini call returned no response")

        text = response.text or ""
        structured = None
        if json_schema is not None and text:
            try:
                structured = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("gemini returned non-JSON despite schema; passing text through")

        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text=text,
            model=model,
            tokens_input=int(getattr(usage, "prompt_token_count", None) or 0) if usage else 0,
            tokens_output=int(getattr(usage, "candidates_token_count", None) or 0) if usage else 0,
            cache_read_tokens=int(getattr(usage, "cached_content_token_count", None) or 0) if usage else 0,
            structured=structured,
        )
