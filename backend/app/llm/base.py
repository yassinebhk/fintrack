"""LLM provider protocol."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    cache_read_tokens: int = 0
    structured: Any = None
    raw: dict = field(default_factory=dict)


class LLMClient(Protocol):
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        ...
