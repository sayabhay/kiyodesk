"""TradeOpportunity persistence model.

A TradeOpportunity is produced by the Trading Runtime when the Strategy Engine
detects a valid ICT Pure OTE setup.  It lives in the trade_opportunities table
and drives the Accept / Reject workflow on the dashboard.

Lifecycle:  ACTIVE → TAKEN | REJECTED | INVALIDATED | EXPIRED
            TAKEN  → COMPLETED
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OpportunityStatus(StrEnum):
    """Valid status values for a TradeOpportunity."""

    NEW = "new"
    ACTIVE = "active"
    TAKEN = "taken"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    COMPLETED = "completed"


class TradeOpportunity(Base):
    """A structured trading opportunity produced by the Strategy Engine."""

    __tablename__ = "trade_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Strategy identification
    strategy: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Setup geometry
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    direction: Mapped[str] = mapped_column(String(10))
    entry: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    take_profit: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    risk_reward: Mapped[Decimal] = mapped_column(Numeric(10, 6))

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default=OpportunityStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Journal link — set when a trade is created from this opportunity
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), nullable=True, index=True)

    # Domain Engine outputs — future engines write here
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )  # null until v0.6
    market_regime: Mapped[str | None] = mapped_column(String(50), nullable=True)  # null until v0.7

    # Full TradeSetup serialized to JSON — immutable audit trail
    trade_setup_json: Mapped[str] = mapped_column(Text)

    # Arbitrary future metadata
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Deduplication tolerance — stored for audit
    entry_tolerance: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0.01"))
