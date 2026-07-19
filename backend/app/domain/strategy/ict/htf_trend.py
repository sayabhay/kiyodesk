"""HTF EMA trend filter — faithful port of the kScript HTF trend logic.

kScript reference
-----------------
    timeseries h4    = htf(source=bars, timeframe=htfTF)
    timeseries h4ema = ema(source=h4.close, period=emaLen)

    var htfBullish = !useHTFTrend || h4ema > h4ema[emaSlopeLen]
    var htfBearish = !useHTFTrend || h4ema < h4ema[emaSlopeLen]

    var longEnabled  = tradeDir != "Short Only"
    var shortEnabled = tradeDir != "Long Only"

Key behavioral rules
--------------------
1. When use_htf_trend=False both htfBullish and htfBearish are True —
   the filter is disabled and all directions pass through.

2. Slope is compared against ema[-1 - slope_lookback]:
   bullish  →  ema[-1] > ema[-1 - slope_lookback]
   bearish  →  ema[-1] < ema[-1 - slope_lookback]

3. EMA formula: standard exponential moving average.
   Multiplier  k = 2 / (period + 1)
   Seed value  = simple mean of the first `period` closes.
   Subsequent  ema[i] = close[i] * k + ema[i-1] * (1 - k)

4. Insufficient data (< period + slope_lookback bars) → return (True, True).
   This matches the kScript's "fail open" behaviour: when there is not enough
   HTF history the filter simply does not block any direction.
"""

from decimal import Decimal

from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig

_TWO = Decimal("2")
_ONE = Decimal("1")


def compute_ema(bars: list[Bar], period: int) -> list[Decimal]:
    """Return an EMA series computed over the close prices of ``bars``.

    The output list has the same length as the input.  Values before the seed
    window (indices 0 .. period-2) are filled with the seed SMA so the list
    is always fully populated and index-safe.

    Parameters
    ----------
    bars:    Bar series in chronological order (oldest first).
    period:  EMA period (number of bars for the initial SMA seed).

    Returns
    -------
    List of Decimal EMA values, one per bar.
    """
    n = len(bars)
    if n == 0:
        return []

    closes = [b.close for b in bars]

    # Not enough bars to form even the seed — return close values as-is.
    if n < period:
        return list(closes)

    k = _TWO / (Decimal(period) + _ONE)
    one_minus_k = _ONE - k

    # Seed: SMA of the first `period` bars.
    seed = sum(closes[:period], Decimal("0")) / Decimal(period)

    ema_values: list[Decimal] = [seed] * period  # pad early indices with seed
    current = seed
    for i in range(period, n):
        current = closes[i] * k + current * one_minus_k
        ema_values.append(current)

    return ema_values


def evaluate_trend(
    htf_bars: list[Bar],
    config: StrategyConfig,
) -> tuple[bool, bool]:
    """Return (htf_bullish, htf_bearish) based on the HTF EMA slope.

    Parameters
    ----------
    htf_bars:  Higher-timeframe bar series in chronological order.
    config:    StrategyConfig carrying use_htf_trend, htf_ema_len,
               and ema_slope_lookback.

    Returns
    -------
    (htf_bullish, htf_bearish) — both True when the filter is disabled or
    when there is insufficient data to evaluate the slope.
    """
    # kScript: !useHTFTrend || ...  → filter off means both pass.
    if not config.use_htf_trend:
        return True, True

    required = config.htf_ema_len + config.ema_slope_lookback
    if len(htf_bars) < required:
        # Fail open — not enough history, do not block any direction.
        return True, True

    ema_values = compute_ema(htf_bars, config.htf_ema_len)

    current_ema = ema_values[-1]
    lookback_ema = ema_values[-1 - config.ema_slope_lookback]

    # kScript: h4ema > h4ema[emaSlopeLen]
    htf_bullish = current_ema > lookback_ema
    # kScript: h4ema < h4ema[emaSlopeLen]
    htf_bearish = current_ema < lookback_ema

    return htf_bullish, htf_bearish
