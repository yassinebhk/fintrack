"""Sanity tests for the Settings loader."""

from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.base_currency == "EUR"
    assert s.llm_provider == "gemini"
    assert s.gemini_model_orchestrator.startswith("gemini-2.5")
    assert s.gemini_model_cheap.startswith("gemini-2.5")


def test_has_helpers_false_when_empty():
    s = Settings(_env_file=None)
    assert s.has_gemini is False
    assert s.has_kraken is False
    assert s.has_telegram is False


def test_has_helpers_true_when_set():
    s = Settings(
        _env_file=None,
        gemini_api_key="x",
        kraken_api_key="a",
        kraken_api_secret="b",
        telegram_bot_token="t",
        telegram_chat_id="c",
    )
    assert s.has_gemini is True
    assert s.has_kraken is True
    assert s.has_telegram is True
