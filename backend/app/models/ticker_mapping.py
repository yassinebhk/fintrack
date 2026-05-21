"""ISIN / problematic ticker → canonical mapping (replaces hardcoded dict)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TickerMapping(Base):
    __tablename__ = "ticker_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_ticker: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    target_ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="yahoo")
    asset_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(256), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
