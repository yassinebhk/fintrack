"""Tests for the Kraken asset code normalizer."""

import pytest

from app.services.brokers.kraken import normalize_kraken_asset


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("XXBT", "BTC"),
        ("XBT", "BTC"),
        ("XETH", "ETH"),
        ("XXDG", "DOGE"),
        ("XDG", "DOGE"),
        ("ZEUR", "EUR"),
        ("ZUSD", "USD"),
        # Modern assets without prefix
        ("PEPE", "PEPE"),
        ("SOL", "SOL"),
        ("ADA", "ADA"),
        # Staking variants
        ("ETH.S", "ETH"),
        ("DOT.S", "DOT"),
    ],
)
def test_normalize(raw: str, expected: str):
    assert normalize_kraken_asset(raw) == expected
