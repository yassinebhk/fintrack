"""Paper-only day-trading journal entries.

Each row is a single discretionary trade the user logged with a written thesis and
a stop-loss, before knowing the outcome. No real money moves here — this exists to
let the user test "informed daily trading" against real market data and a passive
benchmark for months, with the same anti-noise honesty as the rest of the app,
before ever considering real capital.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DayTrade(Base):
    __tablename__ = "day_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="")
    direction: Mapped[str] = mapped_column(String(8), default="long")  # long | short
    conviction: Mapped[str] = mapped_column(String(16), default="media")  # alta | media | baja

    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    news_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    stake_eur: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    benchmark_ticker: Mapped[str] = mapped_column(String(32), default="EUNL.DE")
    bench_price_at_open: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)  # open | closed
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # stop_loss | take_profit | manual | time_exit
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    bench_price_at_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    bench_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_day_trade_ticker", "ticker"),
        Index("ix_day_trade_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<DayTrade {self.ticker} {self.direction} status={self.status}>"
