"""Tests for the snapshots repository."""

from datetime import date, timedelta

import pytest

from app.repositories import SnapshotRepository


@pytest.mark.asyncio
async def test_upsert_today(session):
    repo = SnapshotRepository(session)
    today = date.today()
    await repo.upsert_today(snapshot_date=today, total_value=1500.0, total_cost=1000.0)
    await session.commit()

    all_snaps = await repo.list_all()
    assert len(all_snaps) == 1
    assert all_snaps[0].total_value == 1500.0


@pytest.mark.asyncio
async def test_upsert_idempotent(session):
    repo = SnapshotRepository(session)
    today = date.today()
    await repo.upsert_today(snapshot_date=today, total_value=1500.0)
    await session.commit()
    await repo.upsert_today(snapshot_date=today, total_value=1600.0)
    await session.commit()

    all_snaps = await repo.list_all()
    assert len(all_snaps) == 1
    assert all_snaps[0].total_value == 1600.0


@pytest.mark.asyncio
async def test_list_last_days(session):
    repo = SnapshotRepository(session)
    today = date.today()
    for n in range(10):
        await repo.upsert_today(snapshot_date=today - timedelta(days=n), total_value=100.0 * n)
    await session.commit()

    recent = await repo.list_last_days(days=5)
    assert len(recent) == 6  # today + 5 prior
