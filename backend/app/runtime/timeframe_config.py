"""Multi-timeframe configuration for the Trading Runtime.

Defines the complete set of valid execution timeframes, the default
LTF → HTF mapping used when no manual override is configured, and the
``resolve_htf`` function that the StrategyRuntime calls on every evaluation.

Design rules
------------
- HTF is always resolved from the execution timeframe, never calculated
  by resampling LTF bars.
- All timeframe strings are Binance Futures interval identifiers.
  Minutes/hours/days/weeks use lowercase suffixes; months use uppercase M.
- When the monthly timeframe (``1M``) is the execution timeframe there is
  no higher institutional timeframe available, so it maps to itself.
  The Strategy Engine's HTF trend filter is effectively bypassed in this
  case because LTF and HTF bars are identical.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Valid timeframes
# ---------------------------------------------------------------------------

VALID_TIMEFRAMES: Final[tuple[str, ...]] = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "12h",
    "1d",
    "1w",
    "1M",
)

# ---------------------------------------------------------------------------
# Default LTF → HTF mapping
# ---------------------------------------------------------------------------

DEFAULT_HTF_MAP: Final[dict[str, str]] = {
    "1m":  "5m",   # scalp → intraday structure
    "3m":  "15m",  # scalp → session structure
    "5m":  "15m",  # scalp → session structure
    "15m": "1h",   # intraday → hourly trend
    "30m": "4h",   # intraday → session trend
    "1h":  "4h",   # intraday → session trend
    "2h":  "12h",  # session → half-day trend
    "4h":  "12h",  # session → half-day trend
    "6h":  "1d",   # session → daily trend
    "12h": "1d",   # half-day → daily trend
    "1d":  "1w",   # daily → weekly trend
    "1w":  "1M",   # weekly → monthly trend
    "1M":  "1M",   # monthly → self (no higher TF; HTF filter bypassed)
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTimeframeError(ValueError):
    """Raised when an unrecognised timeframe string is supplied."""

    def __init__(self, timeframe: str, context: str = "timeframe") -> None:
        valid = ", ".join(VALID_TIMEFRAMES)
        super().__init__(
            f"Invalid {context} {timeframe!r}. "
            f"Supported timeframes: {valid}"
        )
        self.timeframe = timeframe


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_htf(execution_timeframe: str, override: str | None = None) -> str:
    """Resolve the Higher Timeframe (HTF) for a given execution timeframe.

    Parameters
    ----------
    execution_timeframe:
        The LTF candle interval used for strategy evaluation
        (e.g. ``"15m"``, ``"1h"``, ``"4h"``).  Must be in
        :data:`VALID_TIMEFRAMES`.
    override:
        Optional manual HTF override.  When provided this value is returned
        directly instead of consulting :data:`DEFAULT_HTF_MAP`.  Must be in
        :data:`VALID_TIMEFRAMES`.

    Returns
    -------
    str
        The resolved HTF interval string (e.g. ``"1h"``, ``"4h"``,
        ``"12h"``).

    Raises
    ------
    InvalidTimeframeError
        If ``execution_timeframe`` is not in :data:`VALID_TIMEFRAMES`, or if
        ``override`` is provided but is not in :data:`VALID_TIMEFRAMES`.

    Examples
    --------
    >>> resolve_htf("15m")
    '1h'
    >>> resolve_htf("1h")
    '4h'
    >>> resolve_htf("1h", override="12h")
    '12h'
    >>> resolve_htf("4h")
    '12h'
    """
    if execution_timeframe not in VALID_TIMEFRAMES:
        raise InvalidTimeframeError(execution_timeframe, context="execution timeframe")

    if override is not None:
        if override not in VALID_TIMEFRAMES:
            raise InvalidTimeframeError(override, context="HTF override")
        return override

    return DEFAULT_HTF_MAP[execution_timeframe]
