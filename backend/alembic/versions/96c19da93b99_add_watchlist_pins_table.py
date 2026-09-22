"""add watchlist_pins table

Revision ID: 96c19da93b99
Revises: 38602b97d672
Create Date: 2026-09-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96c19da93b99'
down_revision: Union[str, None] = '38602b97d672'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist_pins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("note", sa.String(280), nullable=True),
    )
    op.create_index("ix_watchlist_pins_user_id", "watchlist_pins", ["user_id"])
    op.create_index("ix_watchlist_pins_ticker", "watchlist_pins", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_pins_ticker", table_name="watchlist_pins")
    op.drop_index("ix_watchlist_pins_user_id", table_name="watchlist_pins")
    op.drop_table("watchlist_pins")
