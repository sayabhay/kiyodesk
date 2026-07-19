"""OTE Zone state machine — faithful port of the kScript OTE zone logic.

kScript reference
-----------------
Bull zone arm (on bosUp):
    bullLegLow    = swingLow
    bullLegHigh   = swingHigh
    bullOTETop    = bullLegHigh - (bullLegHigh - bullLegLow) * oteStart
    bullOTEBottom = bullLegHigh - (bullLegHigh - bullLegLow) * oteEnd
    bullSL        = bullLegLow * (1 - slBufferPerc / 100)
    waitingBull   = true
    waitingBear   = false          ← opposing zone always cancelled

Bear zone arm (on bosDown):
    bearLegHigh   = swingHigh
    bearLegLow    = swingLow
    bearOTEBottom = bearLegLow + (bearLegHigh - bearLegLow) * oteStart
    bearOTETop    = bearLegLow + (bearLegHigh - bearLegLow) * oteEnd
    bearSL        = bearLegHigh * (1 + slBufferPerc / 100)
    waitingBear   = true
    waitingBull   = false

Zone invalidation:
    if invalidateOnClose && waitingBull && bars.close < bullSL  → waitingBull = false
    if invalidateOnClose && waitingBear && bars.close > bearSL  → waitingBear = false

Entry tap (bull):
    tapBull     = waitingBull && bars.low <= bullOTETop && bars.high >= bullOTEBottom
    confirmBull = tapBull && (!requireCloseBack || bars.close >= bullOTEBottom)

Entry tap (bear):
    tapBear     = waitingBear && bars.high >= bearOTEBottom && bars.low <= bearOTETop
    confirmBear = tapBear && (!requireCloseBack || bars.close <= bearOTETop)

Design notes
------------
- ZoneState is a plain dataclass (mutable).  update_zone() returns a *new*
  instance — the caller is responsible for storing it; the orignal is not
  mutated.  This matches the functional style used throughout the engine.
- compute_bull_zone / compute_bear_zone are pure functions with no side effects.
- All arithmetic uses Decimal throughout to preserve precision.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig

_HUNDRED = Decimal("100")


@dataclass
class ZoneState:
    """Mutable snapshot of the OTE zone state machine.

    One instance per StrategyEngine (one per symbol/timeframe).
    Fields are updated by calling update_zone() which returns a new instance.
    """

    waiting_bull: bool = False
    waiting_bear: bool = False

    # Bull zone geometry
    bull_leg_low: Decimal | None = None
    bull_leg_high: Decimal | None = None
    bull_ote_top: Decimal | None = None
    bull_ote_bottom: Decimal | None = None
    bull_sl: Decimal | None = None

    # Bear zone geometry
    bear_leg_low: Decimal | None = None
    bear_leg_high: Decimal | None = None
    bear_ote_top: Decimal | None = None
    bear_ote_bottom: Decimal | None = None
    bear_sl: Decimal | None = None


def compute_bull_zone(
    leg_low: Decimal,
    leg_high: Decimal,
    config: StrategyConfig,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (ote_top, ote_bottom, sl) for a bullish OTE zone.

    kScript:
        bullOTETop    = bullLegHigh - (bullLegHigh - bullLegLow) * oteStart
        bullOTEBottom = bullLegHigh - (bullLegHigh - bullLegLow) * oteEnd
        bullSL        = bullLegLow * (1 - slBufferPerc / 100)
    """
    leg_range = leg_high - leg_low
    ote_top = leg_high - leg_range * config.ote_start
    ote_bottom = leg_high - leg_range * config.ote_end
    sl = leg_low * (Decimal("1") - config.sl_buffer_pct / _HUNDRED)
    return ote_top, ote_bottom, sl


def compute_bear_zone(
    leg_low: Decimal,
    leg_high: Decimal,
    config: StrategyConfig,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (ote_top, ote_bottom, sl) for a bearish OTE zone.

    kScript:
        bearOTEBottom = bearLegLow + (bearLegHigh - bearLegLow) * oteStart
        bearOTETop    = bearLegLow + (bearLegHigh - bearLegLow) * oteEnd
        bearSL        = bearLegHigh * (1 + slBufferPerc / 100)
    """
    leg_range = leg_high - leg_low
    ote_bottom = leg_low + leg_range * config.ote_start
    ote_top = leg_low + leg_range * config.ote_end
    sl = leg_high * (Decimal("1") + config.sl_buffer_pct / _HUNDRED)
    return ote_top, ote_bottom, sl


def update_zone(
    state: ZoneState,
    bos_up: bool,
    bos_down: bool,
    swing_high: Decimal | None,
    swing_low: Decimal | None,
    current_bar: Bar,
    config: StrategyConfig,
    long_enabled: bool,
    short_enabled: bool,
    htf_bullish: bool,
    htf_bearish: bool,
) -> ZoneState:
    """Apply one bar's BOS signals and price action to the zone state machine.

    Returns a new ZoneState; the input state is not modified.

    Processing order (matches kScript evaluation order):
    1. Arm bull zone on bosUp (if long_enabled and htf_bullish).
    2. Arm bear zone on bosDown (if short_enabled and htf_bearish).
    3. Apply zone invalidation based on current bar close.
    """
    s = replace(state)  # shallow copy — all fields are immutable scalars

    # --- Step 1: arm bull zone on bullish BOS ---
    if bos_up and long_enabled and htf_bullish and swing_high is not None and swing_low is not None:
        ote_top, ote_bottom, sl = compute_bull_zone(swing_low, swing_high, config)
        s = replace(
            s,
            waiting_bull=True,
            waiting_bear=False,  # kScript: waitingBear = false
            bull_leg_low=swing_low,
            bull_leg_high=swing_high,
            bull_ote_top=ote_top,
            bull_ote_bottom=ote_bottom,
            bull_sl=sl,
        )

    # --- Step 2: arm bear zone on bearish BOS ---
    if (  # noqa: E501
        bos_down
        and short_enabled
        and htf_bearish
        and swing_high is not None
        and swing_low is not None
    ):
        ote_top, ote_bottom, sl = compute_bear_zone(swing_low, swing_high, config)
        s = replace(
            s,
            waiting_bear=True,
            waiting_bull=False,  # kScript: waitingBull = false
            bear_leg_low=swing_low,
            bear_leg_high=swing_high,
            bear_ote_top=ote_top,
            bear_ote_bottom=ote_bottom,
            bear_sl=sl,
        )

    # --- Step 3: invalidate zones whose structure has failed ---
    if config.invalidate_on_close:
        if s.waiting_bull and s.bull_sl is not None and current_bar.close < s.bull_sl:
            s = replace(s, waiting_bull=False)
        if s.waiting_bear and s.bear_sl is not None and current_bar.close > s.bear_sl:
            s = replace(s, waiting_bear=False)

    return s


def check_tap(
    state: ZoneState,
    bar: Bar,
    config: StrategyConfig,
) -> tuple[bool, bool]:
    """Return (confirm_bull, confirm_bear) for the given bar against the active zones.

    kScript:
        tapBull     = waitingBull && bars.low <= bullOTETop && bars.high >= bullOTEBottom
        confirmBull = tapBull && (!requireCloseBack || bars.close >= bullOTEBottom)

        tapBear     = waitingBear && bars.high >= bearOTEBottom && bars.low <= bearOTETop
        confirmBear = tapBear && (!requireCloseBack || bars.close <= bearOTETop)
    """
    confirm_bull = False
    confirm_bear = False

    if state.waiting_bull and state.bull_ote_top is not None and state.bull_ote_bottom is not None:
        tap_bull = bar.low <= state.bull_ote_top and bar.high >= state.bull_ote_bottom
        if tap_bull:
            if config.require_close_back:
                confirm_bull = bar.close >= state.bull_ote_bottom
            else:
                confirm_bull = True

    if state.waiting_bear and state.bear_ote_top is not None and state.bear_ote_bottom is not None:
        tap_bear = bar.high >= state.bear_ote_bottom and bar.low <= state.bear_ote_top
        if tap_bear:
            if config.require_close_back:
                confirm_bear = bar.close <= state.bear_ote_top
            else:
                confirm_bear = True

    return confirm_bull, confirm_bear
