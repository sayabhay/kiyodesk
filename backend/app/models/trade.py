"""Trade journal persistence model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Trade(Base):
    """A manually journaled trade and its lifecycle values."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    profit_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    profit_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
