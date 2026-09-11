"""One-off reconstruction of FinTrack's 20-position portfolio after Neon Postgres
exhausted its free compute quota (2026-09-11) and blocked all connections, including
pg_dump, making the real production data unrecoverable. Rebuilt from the last known
good snapshot (2026-09-03) hardcoded in tools/daily_status.py — the standalone
Telegram bot that never depended on Render/Neon.

Run once, from backend/, inside the venv: ./.venv/bin/python3 reconstruct_portfolio.py
"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.db import SessionLocal, init_db
from app.models.position import Position

# (ticker, name, qty, total_cost_eur, kind, price_symbol, last_snapshot_value_eur)
POS = [
    ("IE00BYX5NX33", "0P0001CLDK.F",                22.415958095113616, 301.37, "yh", "0P0001CLDK.F", 316.00),
    ("IE00B4ND3602", "iShares Physical Gold",       1.532456,           122.00, "yh", "PPFB.DE",      115.15),
    ("BTC",          "BTC",                          0.00154958,        140.61, "cg", "bitcoin",      108.54),
    ("BTEC.L",       "BTEC.L",                       12.408661949165698, 124.46, "yh", "BTEC.L",       107.29),
    ("LYX0F.DE",     "LYX0F.DE",                     0.982512,           97.00,  "yh", "UST.PA",       97.00),
    ("MU",           "Micron Technology Inc.",       0.06381010113901031, 60.00, "yh", "MU",           60.00),
    ("QDVF.DE",      "QDVF.DE",                      4.835589,           51.00,  "yh", "QDVF.DE",      57.13),
    ("COPX.L",       "COPX.L",                       0.81726,            59.39,  "yh", "COPX.L",       50.52),
    ("VVSM.DE",      "VVSM.DE",                      0.51261,            51.00,  "yh", "VVSM.DE",      44.99),
    ("ZPDU.DE",      "SSSPDR S+P US Ut..Sel.Se.UETF R", 0.8743169398907104, 40.00, "yh", "ZPDU.DE",   40.92),
    ("PLTR",         "Palantir Technologies Inc.",   0.177841,           24.30,  "yh", "PLTR",         27.98),
    ("NUKL.DE",      "NUKL.DE",                      0.382921,           21.00,  "yh", "NUKL.DE",      18.08),
    ("SPCX",         "Space Exploration",            0.137756,           30.13,  "yh", "SPCX",         17.78),
    ("USPY.DE",      "USPY.DE",                      0.385306,           16.00,  "yh", "USPY.DE",      16.00),
    ("IEAA.L",       "ISHARES III PLC ISH CORE EUR CO", 2.787068,        16.00,  "yh", "IEAA.L",       14.93),
    ("JEDI.DE",      "JEDI.DE",                      0.192012,           21.00,  "yh", "JEDI.DE",      13.05),
    ("PEPE",         "PEPE",                         1355888.11,         5.99,   "cg", "pepe",         4.38),
    ("ETH",          "ETH",                          0.0005662118,       1.72,   "cg", "ethereum",     1.22),
    ("SOL",          "SOL",                          0.0065541103,       0.87,   "cg", "solana",       0.59),
    ("DOGE",         "DOGE",                         1.251478,           0.21,   "cg", "dogecoin",     0.10),
]

CRYPTO = {"BTC", "ETH", "SOL", "DOGE", "PEPE"}
STOCK = {"MU", "PLTR"}


def classify(ticker: str) -> str:
    if ticker in CRYPTO:
        return "crypto"
    if ticker in STOCK:
        return "stock"
    if ticker.startswith("IE00"):
        return "fund" if ticker == "IE00BYX5NX33" else "etf"
    return "etf"


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        for ticker, name, qty, total_cost, kind, sym, snap in POS:
            broker = "kraken" if ticker in CRYPTO else "trade_republic"
            source = "kraken_api" if ticker in CRYPTO else "manual"
            pos = Position(
                ticker=ticker,
                quantity=qty,
                avg_price=total_cost / qty,
                type=classify(ticker),
                currency="EUR",
                broker=broker,
                asset_name=name,
                source=source,
            )
            session.add(pos)
        await session.commit()
    print(f"Inserted {len(POS)} positions.")


if __name__ == "__main__":
    asyncio.run(main())
