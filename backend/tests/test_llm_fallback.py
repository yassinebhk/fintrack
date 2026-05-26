"""Tests for the LLM fallback client (Gemini → Groq on quota errors)."""

import pytest

from app.llm.base import LLMMessage, LLMResponse
from app.llm.factory import FallbackLLMClient, _should_fallback


class _Raises:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def generate(self, messages, **kwargs):
        raise self.exc


class _Returns:
    def __init__(self, model: str):
        self.model = model

    async def generate(self, messages, **kwargs):
        return LLMResponse(text="ok", model=self.model, tokens_input=1, tokens_output=1)


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("429 RESOURCE_EXHAUSTED", True),
        ("quota exceeded", True),
        ("503 UNAVAILABLE", True),
        ("500 internal", True),
        ("invalid json schema", False),
        ("connection refused", False),
    ],
)
def test_should_fallback(msg, expected):
    assert _should_fallback(Exception(msg)) is expected


@pytest.mark.asyncio
async def test_fallback_on_quota():
    fb = FallbackLLMClient(_Raises(RuntimeError("429 quota")), _Returns("groq-model"), "gemini", "groq")
    r = await fb.generate([LLMMessage(role="user", content="hi")])
    assert r.model == "groq-model"


@pytest.mark.asyncio
async def test_no_fallback_on_other_error():
    fb = FallbackLLMClient(_Raises(ValueError("bad schema")), _Returns("groq-model"), "gemini", "groq")
    with pytest.raises(ValueError):
        await fb.generate([LLMMessage(role="user", content="hi")])


@pytest.mark.asyncio
async def test_primary_success_no_fallback():
    fb = FallbackLLMClient(_Returns("gemini-model"), _Returns("groq-model"), "gemini", "groq")
    r = await fb.generate([LLMMessage(role="user", content="hi")])
    assert r.model == "gemini-model"
