"""Break of Structure detection — faithful port of the kScript BOS logic.

kScript reference
-----------------
    var bosUp   = !isna(swingHigh) && bars.close > swingHigh && bars.close[1] <= swingHigh
    var bosDown = !isna(swingLow)  && bars.close < swingLow  && bars.close[1] >= swingLow

The kScript uses a manual crossover check rather than a library crossover()
call because swingHigh/swingLow are persist scalars, not timeseries.

bosUp   fires on the bar where close crosses *above* swingHigh:
        current close > swingHigh  AND  prior close <= swingHigh

bosDown fires on the bar where close crosses *below* swingLow:
        current close < swingLow   AND  prior close >= swingLow

At least 2 bars are required (current + one prior bar).
"""

from decimal import Decimal

from app.domain.strategy.interfaces.bar import Bar


def detect_bos(
    bars: list[Bar],
    swing_high: Decimal | None,
    swing_low: Decimal | None,
) -> tuple[bool, bool]:
    """Return (bos_up, bos_down) for the most recent bar in the series.

    Parameters
    ----------
    bars:        Bar series in chronological order (oldest first).
                 Must contain at least 2 bars; returns (False, False) otherwise.
    swing_high:  Most recently confirmed swing high (from detect_pivots).
                 None means no confirmed pivot exists — BOS cannot fire.
    swing_low:   Most recently confirmed swing low.
                 None means no confirmed pivot exists — BOS cannot fire.

    Returns
    -------
    (bos_up, bos_down) — at most one will be True per call given that a single
    bar cannot simultaneously cross above a swing high and below a swing low
    (swing_high > swing_low by construction).
    """
    if len(bars) < 2:
        return False, False

    current_close = bars[-1].close
    prior_close = bars[-2].close

    # kScript: bars.close > swingHigh && bars.close[1] <= swingHigh
    bos_up = swing_high is not None and current_close > swing_high and prior_close <= swing_high

    # kScript: bars.close < swingLow && bars.close[1] >= swingLow
    bos_down = swing_low is not None and current_close < swing_low and prior_close >= swing_low

    return bos_up, bos_down
