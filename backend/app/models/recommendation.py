"""Out-of-sample tracking of every opportunity the system recommends.

This is the honesty backbone: we snapshot each recommendation at the moment it's
made (ticker, scores, price, benchmark price) and later fill in how it actually
did at 1/3/6 months — both absolute and vs its benchmark (alpha). Aggregating
these tells us, with data, whether the engine adds value or is noise.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RecommendationTrack(Base):
    __tablename__ = "recommendation_track"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rec_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="")
    approach: Mapped[str] = mapped_column(String(16), default="")       # momentum / valor / contrarian
    conviction: Mapped[str] = mapped_column(String(16), default="")     # alta / media / baja
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    price_at_rec: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_ticker: Mapped[str] = mapped_column(String(32), default="")
    bench_price_at_rec: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Forward returns (%), filled later by the evaluator. NULL = not yet due.
    ret_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_6m: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_1m: Mapped[float | None] = mapped_column(Float, nullable=True)   # vs benchmark
    excess_3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_6m: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # One snapshot per ticker per day (re-running generation the same day is idempotent).
    __table_args__ = (
        UniqueConstraint("rec_date", "ticker", name="uq_rec_date_ticker"),
    )
