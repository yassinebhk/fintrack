"""Reasoned trade journal — a REAL decision logged with its rationale, then closed
later with the outcome and a written lesson. The review loop (thesis → outcome →
lesson) is what separates a real trader's journal from a raw transaction log, and
is the habit that most improves decision quality over time. No money moves here;
it's a record of *why* you decided something and *what you learned*."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    ticker: Mapped[str] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    action: Mapped[str] = mapped_column(String(16), default="compra")   # compra|venta|mantener|vigilar
    conviction: Mapped[str] = mapped_column(String(16), default="media")  # alta|media|baja
    horizon: Mapped[str] = mapped_column(String(48), default="")

    thesis: Mapped[str] = mapped_column(Text, nullable=False)            # WHY — written before the outcome
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # market price snapshot at log time

    # Review loop — filled in later, when you look back.
    status: Mapped[str] = mapped_column(String(16), default="abierta", nullable=False)  # abierta|revisada
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)  # acierto|fallo|neutral
    lesson: Mapped[str | None] = mapped_column(Text, nullable=True)         # WHAT YOU LEARNED
