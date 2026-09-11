"""Holdings currently in the portfolio."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # stock, etf, fund, crypto
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    broker: Mapped[str] = mapped_column(String(32), nullable=False)

    isin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    # manual | kraken_api | tr_pytr | pdf_import | csv_import

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "broker", name="uq_position_user_ticker_broker"),
        Index("ix_position_broker", "broker"),
        Index("ix_position_type", "type"),
        Index("ix_position_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Position {self.ticker} ({self.broker}) qty={self.quantity}>"
