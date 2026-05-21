"""One-shot migration: CSV + JSON → SQLite.

Run with:  python -m app.scripts.migrate_legacy

Safe to re-run: positions are upserted by (ticker, broker), snapshots by date,
ticker_mappings by source_ticker.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from app.config import BACKEND_DIR
from app.db import init_db, session_scope
from app.logging_config import setup_logging
from app.repositories import (
    PositionRepository,
    SnapshotRepository,
    TickerMappingRepository,
)


# Seed for ticker_mappings — moved here from yahoo_finance.py TICKER_MAPPING
SEED_TICKER_MAPPINGS: list[dict] = [
    {
        "source_ticker": "LYX0F.DE",
        "target_ticker": "UST.PA",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "Amundi Nasdaq-100 (Paris listing)",
        "notes": "Original Xetra listing returns no data — Paris equivalent works",
    },
    {
        "source_ticker": "IE00BYX5NX33",
        "target_ticker": "0P0001CLDK.F",
        "provider": "yahoo",
        "asset_type": "fund",
        "asset_name": "Fidelity MSCI World P-ACC EUR (Frankfurt)",
        "notes": "ISIN → Frankfurt listing",
    },
    {
        "source_ticker": "SGLD.L",
        "target_ticker": "PPFB.DE",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "iShares Physical Gold ETC (Xetra)",
    },
    {
        "source_ticker": "IE00B4ND3602",
        "target_ticker": "PPFB.DE",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "iShares Physical Gold ETC (Xetra) — by ISIN",
    },
    {
        "source_ticker": "SWDA.L",
        "target_ticker": "SWDA.L",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "iShares MSCI World",
    },
    {
        "source_ticker": "VWCE.DE",
        "target_ticker": "VWCE.DE",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "Vanguard FTSE All-World",
    },
    {
        "source_ticker": "EUNL.DE",
        "target_ticker": "EUNL.DE",
        "provider": "yahoo",
        "asset_type": "etf",
        "asset_name": "iShares MSCI World EUR",
    },
]


SEED_CRYPTO_MAPPINGS: list[dict] = [
    {"source_ticker": "BTC", "target_ticker": "bitcoin", "provider": "coingecko"},
    {"source_ticker": "ETH", "target_ticker": "ethereum", "provider": "coingecko"},
    {"source_ticker": "SOL", "target_ticker": "solana", "provider": "coingecko"},
    {"source_ticker": "ADA", "target_ticker": "cardano", "provider": "coingecko"},
    {"source_ticker": "DOT", "target_ticker": "polkadot", "provider": "coingecko"},
    {"source_ticker": "AVAX", "target_ticker": "avalanche-2", "provider": "coingecko"},
    {"source_ticker": "MATIC", "target_ticker": "matic-network", "provider": "coingecko"},
    {"source_ticker": "LINK", "target_ticker": "chainlink", "provider": "coingecko"},
    {"source_ticker": "UNI", "target_ticker": "uniswap", "provider": "coingecko"},
    {"source_ticker": "ATOM", "target_ticker": "cosmos", "provider": "coingecko"},
    {"source_ticker": "XRP", "target_ticker": "ripple", "provider": "coingecko"},
    {"source_ticker": "DOGE", "target_ticker": "dogecoin", "provider": "coingecko"},
    {"source_ticker": "SHIB", "target_ticker": "shiba-inu", "provider": "coingecko"},
    {"source_ticker": "PEPE", "target_ticker": "pepe", "provider": "coingecko"},
    {"source_ticker": "LTC", "target_ticker": "litecoin", "provider": "coingecko"},
    {"source_ticker": "BCH", "target_ticker": "bitcoin-cash", "provider": "coingecko"},
    {"source_ticker": "XLM", "target_ticker": "stellar", "provider": "coingecko"},
    {"source_ticker": "ALGO", "target_ticker": "algorand", "provider": "coingecko"},
    {"source_ticker": "VET", "target_ticker": "vechain", "provider": "coingecko"},
    {"source_ticker": "FIL", "target_ticker": "filecoin", "provider": "coingecko"},
    {"source_ticker": "AAVE", "target_ticker": "aave", "provider": "coingecko"},
    {"source_ticker": "XMR", "target_ticker": "monero", "provider": "coingecko"},
    {"source_ticker": "ETC", "target_ticker": "ethereum-classic", "provider": "coingecko"},
    {"source_ticker": "NEAR", "target_ticker": "near", "provider": "coingecko"},
    {"source_ticker": "ARB", "target_ticker": "arbitrum", "provider": "coingecko"},
    {"source_ticker": "OP", "target_ticker": "optimism", "provider": "coingecko"},
]


async def migrate_positions(csv_path: Path) -> int:
    if not csv_path.exists():
        logger.warning("positions CSV not found at {}, skipping", csv_path)
        return 0

    df = pd.read_csv(csv_path)
    df["ticker"] = df["ticker"].str.upper().str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["avg_price"] = pd.to_numeric(df["avg_price"], errors="coerce")
    df = df.dropna(subset=["quantity", "avg_price"])

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "ticker": r["ticker"],
            "quantity": float(r["quantity"]),
            "avg_price": float(r["avg_price"]),
            "type": str(r["type"]).lower(),
            "currency": str(r["currency"]).upper(),
            "broker": str(r["broker"]),
            "source": "csv_legacy",
        })

    async with session_scope() as session:
        repo = PositionRepository(session)
        count = await repo.bulk_upsert(rows)
        logger.info("migrated {} positions from {}", count, csv_path.name)
    return count


async def migrate_snapshots(json_path: Path) -> int:
    if not json_path.exists():
        logger.warning("snapshots JSON not found at {}, skipping", json_path)
        return 0

    with json_path.open() as f:
        data = json.load(f)
    values = data.get("values", [])
    if not values:
        return 0

    count = 0
    async with session_scope() as session:
        repo = SnapshotRepository(session)
        for entry in values:
            snap_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            await repo.upsert_today(
                snapshot_date=snap_date,
                total_value=float(entry["value"]),
            )
            count += 1
    logger.info("migrated {} portfolio snapshots", count)
    return count


async def seed_ticker_mappings() -> int:
    async with session_scope() as session:
        repo = TickerMappingRepository(session)
        seeds = SEED_TICKER_MAPPINGS + SEED_CRYPTO_MAPPINGS
        for m in seeds:
            await repo.upsert(**m)
    logger.info("seeded {} ticker mappings", len(SEED_TICKER_MAPPINGS) + len(SEED_CRYPTO_MAPPINGS))
    return len(SEED_TICKER_MAPPINGS) + len(SEED_CRYPTO_MAPPINGS)


async def main() -> None:
    setup_logging()
    logger.info("=== FinTrack legacy migration ===")

    logger.info("step 1: init_db (create tables)")
    await init_db()

    logger.info("step 2: seed ticker mappings")
    await seed_ticker_mappings()

    logger.info("step 3: migrate positions.csv")
    await migrate_positions(BACKEND_DIR / "data" / "positions.csv")

    logger.info("step 4: migrate historical_values.json")
    await migrate_snapshots(BACKEND_DIR / "data" / "historical_values.json")

    logger.info("✅ migration complete")


if __name__ == "__main__":
    asyncio.run(main())
