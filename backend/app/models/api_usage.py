"""API quota usage audit persistence model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ApiUsage(Base):
    """One external API request for quota reporting and enforcement."""

    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
