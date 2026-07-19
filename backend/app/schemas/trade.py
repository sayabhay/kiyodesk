"""Trade journal request and response schemas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.market import MarketSnapshot


class TradeDirection(StrEnum):
    """Supported discretionary trade directions."""

    LONG = "long"
    SHORT = "short"


class CreateTradeRequest(BaseModel):
    """Manual trade entry supplied after a KScript signal is visible on the chart."""

    symbol: str = Field(min_length=2, max_length=30)
    direction: TradeDirection
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    timeframe: str | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=5000)
    strategy_version: str | None = Field(default=None, max_length=100)


class CloseTradeRequest(BaseModel):
    """Exit price supplied when manually closing a journaled trade."""

    exit_price: Decimal = Field(gt=0)


class TradeResponse(BaseModel):
    """A persisted journal trade with the entry-time market snapshot."""

    id: int
    symbol: str
    direction: TradeDirection
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    exit_price: Decimal | None
    status: str
    profit_loss: Decimal | None
    profit_loss_pct: Decimal | None
    timeframe: str | None
    notes: str | None
    strategy_version: str | None
    created_at: datetime
    closed_at: datetime | None
    market_snapshot: MarketSnapshot | None = None
