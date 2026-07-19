"""Normalized OHLCV bar — the common input unit for all Domain Engine modules."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Bar:
    """A single OHLCV candlestick bar.

    All price and volume fields use Decimal for arithmetic precision.
    The timestamp should be timezone-aware (UTC preferred).
    """

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
