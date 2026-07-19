"""Swing pivot detection — faithful port of the kScript pivothigh/pivotlow logic.

kScript reference
-----------------
    timeseries ph = pivothigh(source=bars, leftbars=swingLen, rightbars=swingLen, priceIndex=2)
    timeseries pl = pivotlow(source=bars, leftbars=swingLen, rightbars=swingLen, priceIndex=3)

    if (!isna(ph)) { swingHigh = ph }
    if (!isna(pl)) { swingLow  = pl }

A pivot high at index i is confirmed when bars[i].high is strictly the highest
high in the window [i - swingLen .. i + swingLen].  A pivot low is the mirror
for the low.

Because rightbars bars must have already closed after the candidate bar, the
most recent index that can possibly be confirmed is len(bars) - 1 - swing_len.
We scan backwards from there and return the most recently confirmed value.
"""

from decimal import Decimal

from app.domain.strategy.interfaces.bar import Bar


def detect_pivots(
    bars: list[Bar],
    swing_len: int,
) -> tuple[Decimal | None, Decimal | None]:
    """Return (swing_high, swing_low) — the most recently confirmed pivot values.

    Parameters
    ----------
    bars:       Bar series in chronological order (oldest first).
    swing_len:  Number of bars required on each side of a pivot candidate.
                Matches kScript ``leftbars`` and ``rightbars``.

    Returns
    -------
    A tuple of (swing_high, swing_low).  Either value is None when no
    confirmed pivot exists within the series.
    """
    min_bars = 2 * swing_len + 1
    if len(bars) < min_bars:
        return None, None

    # The last index that has swing_len confirmed bars to its right.
    last_candidate = len(bars) - 1 - swing_len

    swing_high: Decimal | None = None
    swing_low: Decimal | None = None

    # Scan newest-to-oldest so we return the most recent confirmed pivot.
    for i in range(last_candidate, swing_len - 1, -1):
        window_start = i - swing_len
        window_end = i + swing_len  # inclusive

        candidate_high = bars[i].high
        candidate_low = bars[i].low

        # Collect the surrounding window (excluding the candidate bar itself).
        surrounding_highs = [bars[j].high for j in range(window_start, window_end + 1) if j != i]
        surrounding_lows = [bars[j].low for j in range(window_start, window_end + 1) if j != i]

        # Strict pivot: candidate must be strictly greater/less than every
        # surrounding bar — ties are not pivots.
        if swing_high is None and all(candidate_high > h for h in surrounding_highs):
            swing_high = candidate_high

        if swing_low is None and all(candidate_low < lo for lo in surrounding_lows):
            swing_low = candidate_low

        # Short-circuit once both are found.
        if swing_high is not None and swing_low is not None:
            break

    return swing_high, swing_low
