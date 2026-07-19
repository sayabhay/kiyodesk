"""Normalized market data persistence model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MarketData(Base):
    """A normalized market data point from a configured provider."""

    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    funding_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 12), nullable=True)
    liquidation_volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
