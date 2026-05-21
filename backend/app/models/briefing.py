"""Daily AI briefing produced by the orchestrator agent."""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)

    headline: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(nullable=True)

    delivered_email: Mapped[bool] = mapped_column(default=False)
    delivered_telegram: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("briefing_date", name="uq_briefing_date"),
    )
