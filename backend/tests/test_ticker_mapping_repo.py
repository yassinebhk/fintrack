"""Tests for the ticker mapping repository."""

import pytest

from app.repositories import TickerMappingRepository


@pytest.mark.asyncio
async def test_resolve_unknown_returns_self(session):
    repo = TickerMappingRepository(session)
    assert await repo.resolve("AAPL") == "AAPL"


@pytest.mark.asyncio
async def test_upsert_and_resolve(session):
    repo = TickerMappingRepository(session)
    await repo.upsert(
        source_ticker="IE00B4ND3602",
        target_ticker="PPFB.DE",
        provider="yahoo",
        asset_name="iShares Physical Gold",
    )
    await session.commit()
    assert await repo.resolve("IE00B4ND3602") == "PPFB.DE"


@pytest.mark.asyncio
async def test_upsert_updates_existing(session):
    repo = TickerMappingRepository(session)
    await repo.upsert(source_ticker="SGLD.L", target_ticker="OLD.DE")
    await session.commit()
    await repo.upsert(source_ticker="SGLD.L", target_ticker="PPFB.DE")
    await session.commit()

    assert await repo.resolve("SGLD.L") == "PPFB.DE"
    rows = await repo.list_all()
    assert len(rows) == 1
