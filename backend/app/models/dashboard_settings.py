"""Persistent dashboard settings for strategy and risk configuration."""

from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DashboardSettings(Base):
    """Singleton row storing dashboard-configurable settings.

    This model is intentionally permissive and stores scalar settings used by
    the Trading Runtime and risk engine. The application treats the first row
    as the active settings; APIs operate against that row.
    """

    __tablename__ = "dashboard_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Symbols and timeframes are stored as CSV strings for simplicity.
    symbols: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeframes: Mapped[str | None] = mapped_column(Text, nullable=True)
    htf_mapping_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Risk configuration
    risk_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    fixed_risk: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    swing_buffer: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    reward_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Risk limits
    max_concurrent_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_daily_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    max_weekly_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    # Execution / account
    execution_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_balance: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)

    # Generic metadata
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
