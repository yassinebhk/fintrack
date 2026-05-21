"""Tests for the positions repository."""

import pytest

from app.repositories import PositionRepository


@pytest.mark.asyncio
async def test_upsert_and_get(session):
    repo = PositionRepository(session)
    pos = await repo.upsert(
        ticker="btc",
        quantity=0.5,
        avg_price=20000.0,
        type="crypto",
        currency="EUR",
        broker="Kraken",
    )
    await session.commit()

    assert pos.ticker == "BTC"
    fetched = await repo.get("BTC", "Kraken")
    assert fetched is not None
    assert fetched.quantity == 0.5


@pytest.mark.asyncio
async def test_upsert_updates_existing(session):
    repo = PositionRepository(session)
    await repo.upsert(
        ticker="BTC", quantity=0.5, avg_price=20000, type="crypto", currency="EUR", broker="Kraken"
    )
    await session.commit()

    await repo.upsert(
        ticker="BTC", quantity=0.7, avg_price=22000, type="crypto", currency="EUR", broker="Kraken"
    )
    await session.commit()

    all_positions = await repo.list_all()
    assert len(all_positions) == 1
    assert all_positions[0].quantity == 0.7
    assert all_positions[0].avg_price == 22000


@pytest.mark.asyncio
async def test_bulk_upsert(session):
    repo = PositionRepository(session)
    rows = [
        {"ticker": "BTC", "quantity": 0.1, "avg_price": 30000, "type": "crypto", "currency": "EUR", "broker": "Kraken"},
        {"ticker": "ETH", "quantity": 1.0, "avg_price": 2000, "type": "crypto", "currency": "EUR", "broker": "Kraken"},
        {"ticker": "VWCE.DE", "quantity": 10, "avg_price": 100, "type": "etf", "currency": "EUR", "broker": "TradeRepublic"},
    ]
    await repo.bulk_upsert(rows)
    await session.commit()

    assert await repo.count() == 3


@pytest.mark.asyncio
async def test_delete_by_broker(session):
    repo = PositionRepository(session)
    rows = [
        {"ticker": "BTC", "quantity": 0.1, "avg_price": 30000, "type": "crypto", "currency": "EUR", "broker": "Kraken"},
        {"ticker": "VWCE.DE", "quantity": 10, "avg_price": 100, "type": "etf", "currency": "EUR", "broker": "TradeRepublic"},
    ]
    await repo.bulk_upsert(rows)
    await session.commit()

    deleted = await repo.delete_by_broker("Kraken")
    await session.commit()
    assert deleted == 1
    assert await repo.count() == 1
