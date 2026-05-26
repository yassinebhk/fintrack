"""Tests for the Polymarket scanner parsing (symbol + target price)."""

import pytest

from app.services.polymarket.scanner import PolymarketScanner


@pytest.fixture
def scanner():
    return PolymarketScanner()


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Will Bitcoin hit $150k by June 30, 2026?", "BTCUSDT"),
        ("Will ETH be above $3,000 by Friday?", "ETHUSDT"),
        ("Roland Garros ATP: Ethan Quinn vs Francisco Comesana", None),  # 'Ethan' must not match 'eth'
        ("Will Netherlands win the 2026 FIFA World Cup?", None),
        ("Will Solana flip Ethereum in 2026?", "SOLUSDT"),  # first mention wins
        ("Dogecoin to $1?", "DOGEUSDT"),
    ],
)
def test_detect_symbol(scanner, question, expected):
    assert scanner._detect_symbol(question) == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Will Bitcoin hit $150k by June 30, 2026?", 150000.0),
        ("Will Bitcoin reach $85,000 in May?", 85000.0),
        ("Will ETH be above $3,000 by Friday?", 3000.0),
        ("Will Netherlands win the 2026 FIFA World Cup?", None),  # year, not a price
        ("MicroStrategy sells any Bitcoin by May 31, 2026?", None),  # no price token
        ("BTC to $1.5M someday?", 1_500_000.0),
    ],
)
def test_extract_target_price(scanner, question, expected):
    assert scanner._extract_target_price(question) == expected
