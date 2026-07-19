"""Normalized market data schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MarketSnapshot(BaseModel):
    """Vendor-neutral market observation returned to application consumers."""

    symbol: str
    provider: str
    captured_at: datetime
    price: Decimal | None = None
    funding_rate: Decimal | None = None
    open_interest: Decimal | None = None
    liquidation_volume: Decimal | None = None
    long_liquidation_volume: Decimal | None = None
    short_liquidation_volume: Decimal | None = None


class MarketHistoryPoint(BaseModel):
    """One stored market observation for charting and historical queries."""

    captured_at: datetime
    price: Decimal | None = None
    funding_rate: Decimal | None = None
    open_interest: Decimal | None = None
    liquidation_volume: Decimal | None = None
    provider: str


class MarketHistoryResponse(BaseModel):
    """Paginated historical market data for a symbol."""

    symbol: str
    points: list[MarketHistoryPoint]
    total: int
