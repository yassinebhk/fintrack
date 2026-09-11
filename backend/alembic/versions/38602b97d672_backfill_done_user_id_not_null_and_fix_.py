"""backfill done; user_id not null and fix unique constraints

Revision ID: 38602b97d672
Revises: 850b2ef2cc88
Create Date: 2026-09-11 19:33:06.863410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38602b97d672'
down_revision: Union[str, None] = '850b2ef2cc88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["positions", "transactions", "day_trades", "snapshots"]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        n = bind.execute(sa.text(f"SELECT count(*) FROM {table} WHERE user_id IS NULL")).scalar_one()
        if n:
            raise RuntimeError(
                f"{table} has {n} row(s) with NULL user_id — run the backfill script "
                "(app/scripts/backfill_owner.py) before applying this migration."
            )

    op.alter_column("positions", "user_id", nullable=False)
    op.drop_constraint("uq_position_ticker_broker", "positions", type_="unique")
    op.create_unique_constraint(
        "uq_position_user_ticker_broker", "positions", ["user_id", "ticker", "broker"]
    )
    op.create_index("ix_position_user_id", "positions", ["user_id"])

    op.alter_column("transactions", "user_id", nullable=False)
    op.drop_constraint("transactions_external_id_key", "transactions", type_="unique")
    op.create_unique_constraint(
        "uq_tx_user_external_id", "transactions", ["user_id", "external_id"]
    )
    op.create_index("ix_tx_user_id", "transactions", ["user_id"])

    op.alter_column("day_trades", "user_id", nullable=False)
    op.create_index("ix_day_trade_user_id", "day_trades", ["user_id"])

    op.alter_column("snapshots", "user_id", nullable=False)
    op.drop_constraint("uq_snapshot_date", "snapshots", type_="unique")
    op.create_unique_constraint("uq_snapshot_user_date", "snapshots", ["user_id", "snapshot_date"])
    op.create_index("ix_snapshot_user_id", "snapshots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_snapshot_user_id", table_name="snapshots")
    op.drop_constraint("uq_snapshot_user_date", "snapshots", type_="unique")
    op.create_unique_constraint("uq_snapshot_date", "snapshots", ["snapshot_date"])
    op.alter_column("snapshots", "user_id", nullable=True)

    op.drop_index("ix_day_trade_user_id", table_name="day_trades")
    op.alter_column("day_trades", "user_id", nullable=True)

    op.drop_index("ix_tx_user_id", table_name="transactions")
    op.drop_constraint("uq_tx_user_external_id", "transactions", type_="unique")
    op.create_unique_constraint("transactions_external_id_key", "transactions", ["external_id"])
    op.alter_column("transactions", "user_id", nullable=True)

    op.drop_index("ix_position_user_id", table_name="positions")
    op.drop_constraint("uq_position_user_ticker_broker", "positions", type_="unique")
    op.create_unique_constraint("uq_position_ticker_broker", "positions", ["ticker", "broker"])
    op.alter_column("positions", "user_id", nullable=True)
