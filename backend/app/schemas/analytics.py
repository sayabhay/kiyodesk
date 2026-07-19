"""Analytics response schemas."""

from decimal import Decimal

from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    """Aggregate performance metrics computed from closed journal trades."""

    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    win_rate: Decimal | None
    """Percentage of closed trades that were profitable (0–100). None when no closed trades."""

    profit_factor: Decimal | None
    """Ratio of gross profit to gross loss. None when no losing trades or no closed trades."""

    expectancy: Decimal | None
    """Average P&L per closed trade in price units. None when no closed trades."""

    total_profit_loss: Decimal | None
    """Sum of all closed trade P&L values. None when no closed trades."""

    average_win: Decimal | None
    """Mean P&L of winning trades. None when no winners."""

    average_loss: Decimal | None
    """Mean P&L of losing trades (negative number). None when no losers."""

    largest_win: Decimal | None
    """Single best trade P&L. None when no winners."""

    largest_loss: Decimal | None
    """Single worst trade P&L (negative number). None when no losers."""
