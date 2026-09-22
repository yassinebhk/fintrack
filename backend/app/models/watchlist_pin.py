"""Watchlist "pins" — a snapshot of a ticker's price at a moment you choose (with
an optional note), so you can compare "what it was when I flagged it" against
now. Distinct from the Watchlist row itself: one ticker can have many pins over
time (no unique constraint), each an independent point-in-time marker."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchlistPin(Base):
    __tablename__ = "watchlist_pins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # The asset's own listing currency (e.g. "USD" for a US stock) — captured
    # alongside price so a pin is never a bare number of ambiguous currency
    # (2026-09-22: exactly the class of bug that caused today's TSM confusion).
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
