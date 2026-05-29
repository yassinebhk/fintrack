"""Generic OpenAI-compatible chat client.

Groq, OpenRouter and Cerebras all speak the OpenAI /chat/completions format, so a
single client parameterized by (base_url, api_key, model) serves them all. Used to
build a multi-provider free fallback chain so we never run out of LLM capacity.
"""

import json

import httpx
from loguru import logger

from app.llm.base import LLMMessage, LLMResponse


class OpenAICompatClient:
    def __init__(self, *, base_url: str, api_key: str, model: str, name: str,
                 supports_json_object: bool = True) -> None:
        if not api_key:
            raise RuntimeError(f"{name}: api key missing")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self.name = name
        self.supports_json_object = supports_json_object

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
        msgs = [{"role": m.role, "content": m.content} for m in messages]

        # No response_schema support → inject schema into the prompt.
        if json_schema is not None:
            schema_str = json.dumps(json_schema, ensure_ascii=False)
            instruction = (
                "\n\nDevuelve EXCLUSIVAMENTE un objeto JSON válido que cumpla este JSON Schema "
                "(usa exactamente esos nombres de campo, sin texto adicional):\n"
                f"{schema_str}"
            )
            if msgs and msgs[-1]["role"] == "user":
                msgs[-1]["content"] += instruction
            else:
                msgs.append({"role": "user", "content": instruction})

        body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if json_schema is not None and self.supports_json_object:
            body["response_format"] = {"type": "json_object"}

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # OpenRouter likes these (optional but recommended).
        if "openrouter" in self.base_url:
            headers["HTTP-Referer"] = "https://fintrack-front.onrender.com"
            headers["X-Title"] = "FinTrack"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("{} call failed: {}", self.name, exc)
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
            text=text, model=f"{self.name}:{model}",
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            structured=structured,
        )
