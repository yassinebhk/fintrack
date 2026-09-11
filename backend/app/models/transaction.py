"""Buy / sell / dividend / fee operations."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    type: Mapped[str] = mapped_column(String(16), nullable=False)  # buy, sell, dividend, fee, deposit, withdrawal
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    broker: Mapped[str] = mapped_column(String(32), nullable=False)

    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tx_ticker_broker", "ticker", "broker"),
        Index("ix_tx_executed_at", "executed_at"),
        Index("ix_tx_type", "type"),
        Index("ix_tx_user_id", "user_id"),
        UniqueConstraint("user_id", "external_id", name="uq_tx_user_external_id"),
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.type} {self.ticker} qty={self.quantity} @ {self.price}>"
