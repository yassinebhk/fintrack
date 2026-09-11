"""One-off Fase-1 migration helper: assign every existing row (positions,
transactions, day_trades, snapshots) to the owner's User account.

Run AFTER the owner has logged in once via Google OAuth (so their User row
exists) and BEFORE applying the second Alembic migration (which makes
user_id NOT NULL). Usage:

    ./.venv/bin/python3 -m app.scripts.backfill_owner owner@example.com
"""

import asyncio
import sys

from sqlalchemy import select, text

from app.db import session_scope
from app.models.user import User

TABLES = ["positions", "transactions", "day_trades", "snapshots"]


async def backfill(email: str) -> None:
    email = email.strip().lower()
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            raise SystemExit(
                f"No user with email {email} found — log in via Google first, then rerun this."
            )
        for table in TABLES:
            result = await session.execute(
                text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": user.id},
            )
            print(f"{table}: assigned {result.rowcount} row(s) to user {user.id} ({email})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 -m app.scripts.backfill_owner <owner-email>")
    asyncio.run(backfill(sys.argv[1]))
