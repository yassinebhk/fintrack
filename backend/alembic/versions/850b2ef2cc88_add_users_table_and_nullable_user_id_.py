"""add users table and nullable user_id columns

Revision ID: 850b2ef2cc88
Revises: 
Create Date: 2026-09-11 19:33:06.212236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '850b2ef2cc88'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("google_sub", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("picture_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])

    # Nullable for now — a data-migration script backfills these to the
    # original owner's new user_id once they've logged in once, then a
    # follow-up migration makes them NOT NULL and fixes the unique constraints.
    op.add_column("positions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("day_trades", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("snapshots", sa.Column("user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("snapshots", "user_id")
    op.drop_column("day_trades", "user_id")
    op.drop_column("transactions", "user_id")
    op.drop_column("positions", "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
