"""Market context captured when a trade is journaled."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TradeSnapshot(Base):
    """A point-in-time market snapshot associated with a trade."""

    __tablename__ = "trade_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    funding_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 12), nullable=True)
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    liquidations: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    market_bias: Mapped[str | None] = mapped_column(String(30), nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
