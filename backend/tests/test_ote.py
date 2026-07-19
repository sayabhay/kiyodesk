"""Unit tests for OTE Zone state machine (Task 5).

kScript canonical behavior verified here:
- Bull zone level arithmetic
- Bear zone level arithmetic
- Zone arming / disarming on BOS
- Zone invalidation on close through SL
- Tap detection (with and without require_close_back)
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.strategy.ict.ote import (
    ZoneState,
    check_tap,
    compute_bear_zone,
    compute_bull_zone,
    update_zone,
)
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(close: str, high: str | None = None, low: str | None = None) -> Bar:
    c = Decimal(close)
    h = Decimal(high) if high else c
    lo = Decimal(low) if low else c
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=c,
        high=h,
        low=lo,
        close=c,
        volume=Decimal("1000"),
    )


def _default_update(
    state: ZoneState,
    *,
    bos_up: bool = False,
    bos_down: bool = False,
    swing_high: Decimal | None = None,
    swing_low: Decimal | None = None,
    current_close: str = "100",
    config: StrategyConfig | None = None,
    long_enabled: bool = True,
    short_enabled: bool = True,
    htf_bullish: bool = True,
    htf_bearish: bool = True,
) -> ZoneState:
    return update_zone(
        state=state,
        bos_up=bos_up,
        bos_down=bos_down,
        swing_high=swing_high,
        swing_low=swing_low,
        current_bar=_bar(current_close),
        config=config or StrategyConfig(),
        long_enabled=long_enabled,
        short_enabled=short_enabled,
        htf_bullish=htf_bullish,
        htf_bearish=htf_bearish,
    )


# ---------------------------------------------------------------------------
# compute_bull_zone arithmetic
# ---------------------------------------------------------------------------


class TestComputeBullZone:
    def test_known_leg_produces_correct_levels(self) -> None:
        """leg_low=100, leg_high=110, ote_start=0.618, ote_end=0.79, sl_buffer=0.05%

        ote_top    = 110 - (110-100)*0.618 = 110 - 6.18 = 103.82
        ote_bottom = 110 - (110-100)*0.79  = 110 - 7.90 = 102.10
        sl         = 100 * (1 - 0.05/100)  = 100 * 0.9995 = 99.95
        """
        config = StrategyConfig()
        ote_top, ote_bottom, sl = compute_bull_zone(Decimal("100"), Decimal("110"), config)
        assert ote_top == Decimal("110") - Decimal("10") * Decimal("0.618")
        assert ote_bottom == Decimal("110") - Decimal("10") * Decimal("0.79")
        assert sl == Decimal("100") * (Decimal("1") - Decimal("0.05") / Decimal("100"))

    def test_ote_top_above_ote_bottom(self) -> None:
        """OTE top (shallower retracement) must be above OTE bottom (deeper)."""
        ote_top, ote_bottom, _ = compute_bull_zone(Decimal("100"), Decimal("110"), StrategyConfig())
        assert ote_top > ote_bottom

    def test_sl_below_leg_low(self) -> None:
        _, _, sl = compute_bull_zone(Decimal("100"), Decimal("110"), StrategyConfig())
        assert sl < Decimal("100")

    def test_zero_buffer_sl_equals_leg_low(self) -> None:
        config = StrategyConfig(sl_buffer_pct=Decimal("0"))
        _, _, sl = compute_bull_zone(Decimal("100"), Decimal("110"), config)
        assert sl == Decimal("100")

    @pytest.mark.parametrize(
        "leg_low,leg_high",
        [
            ("63000", "65000"),
            ("1000", "1200"),
            ("50000", "55000"),
        ],
    )
    def test_levels_within_leg_range(self, leg_low: str, leg_high: str) -> None:
        lo, hi = Decimal(leg_low), Decimal(leg_high)
        ote_top, ote_bottom, sl = compute_bull_zone(lo, hi, StrategyConfig())
        assert lo <= ote_bottom < ote_top <= hi
        assert sl < lo


# ---------------------------------------------------------------------------
# compute_bear_zone arithmetic
# ---------------------------------------------------------------------------


class TestComputeBearZone:
    def test_known_leg_produces_correct_levels(self) -> None:
        """leg_low=100, leg_high=110, ote_start=0.618, ote_end=0.79, sl_buffer=0.05%

        ote_bottom = 100 + (110-100)*0.618 = 100 + 6.18 = 106.18
        ote_top    = 100 + (110-100)*0.79  = 100 + 7.90 = 107.90
        sl         = 110 * (1 + 0.05/100)  = 110 * 1.0005 = 110.055
        """
        config = StrategyConfig()
        ote_top, ote_bottom, sl = compute_bear_zone(Decimal("100"), Decimal("110"), config)
        assert ote_bottom == Decimal("100") + Decimal("10") * Decimal("0.618")
        assert ote_top == Decimal("100") + Decimal("10") * Decimal("0.79")
        assert sl == Decimal("110") * (Decimal("1") + Decimal("0.05") / Decimal("100"))

    def test_ote_top_above_ote_bottom(self) -> None:
        ote_top, ote_bottom, _ = compute_bear_zone(Decimal("100"), Decimal("110"), StrategyConfig())
        assert ote_top > ote_bottom

    def test_sl_above_leg_high(self) -> None:
        _, _, sl = compute_bear_zone(Decimal("100"), Decimal("110"), StrategyConfig())
        assert sl > Decimal("110")

    def test_zero_buffer_sl_equals_leg_high(self) -> None:
        config = StrategyConfig(sl_buffer_pct=Decimal("0"))
        _, _, sl = compute_bear_zone(Decimal("100"), Decimal("110"), config)
        assert sl == Decimal("110")

    @pytest.mark.parametrize(
        "leg_low,leg_high",
        [
            ("63000", "65000"),
            ("1000", "1200"),
            ("50000", "55000"),
        ],
    )
    def test_levels_within_leg_range(self, leg_low: str, leg_high: str) -> None:
        lo, hi = Decimal(leg_low), Decimal(leg_high)
        ote_top, ote_bottom, sl = compute_bear_zone(lo, hi, StrategyConfig())
        assert lo <= ote_bottom < ote_top <= hi
        assert sl > hi


# ---------------------------------------------------------------------------
# update_zone — arming / disarming
# ---------------------------------------------------------------------------


class TestUpdateZone:
    def test_initial_state_is_clean(self) -> None:
        s = ZoneState()
        assert s.waiting_bull is False
        assert s.waiting_bear is False

    def test_bos_up_arms_bull_zone(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
        )
        assert s.waiting_bull is True
        assert s.bull_leg_low == Decimal("100")
        assert s.bull_leg_high == Decimal("110")
        assert s.bull_ote_top is not None
        assert s.bull_ote_bottom is not None
        assert s.bull_sl is not None

    def test_bos_up_disarms_bear_zone(self) -> None:
        """Arming the bull zone always cancels any waiting bear zone (kScript rule)."""
        # First arm bear
        s = _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
        )
        assert s.waiting_bear is True
        # Now BOS up — bear should be cancelled.
        # current_close="115" is above the new bull SL (leg_low=108 * 0.9995 ≈ 107.946)
        # so invalidation does not fire immediately after arming.
        s = _default_update(
            s,
            bos_up=True,
            swing_high=Decimal("120"),
            swing_low=Decimal("108"),
            current_close="115",
        )
        assert s.waiting_bull is True
        assert s.waiting_bear is False

    def test_bos_down_arms_bear_zone(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
        )
        assert s.waiting_bear is True
        assert s.bear_leg_low == Decimal("100")
        assert s.bear_leg_high == Decimal("110")
        assert s.bear_ote_top is not None
        assert s.bear_ote_bottom is not None
        assert s.bear_sl is not None

    def test_bos_down_disarms_bull_zone(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
        )
        assert s.waiting_bull is True
        s = _default_update(
            s,
            bos_down=True,
            swing_high=Decimal("105"),
            swing_low=Decimal("90"),
        )
        assert s.waiting_bear is True
        assert s.waiting_bull is False

    def test_bos_up_suppressed_when_long_disabled(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            long_enabled=False,
        )
        assert s.waiting_bull is False

    def test_bos_down_suppressed_when_short_disabled(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            short_enabled=False,
        )
        assert s.waiting_bear is False

    def test_bos_up_suppressed_when_htf_bearish(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            htf_bullish=False,
        )
        assert s.waiting_bull is False

    def test_bos_down_suppressed_when_htf_bullish(self) -> None:
        s = _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            htf_bearish=False,
        )
        assert s.waiting_bear is False

    def test_no_bos_does_not_change_waiting_state(self) -> None:
        s0 = ZoneState()
        s1 = _default_update(s0)
        assert s1.waiting_bull is False
        assert s1.waiting_bear is False

    def test_input_state_not_mutated(self) -> None:
        """update_zone must return a new instance; never mutate the input."""
        original = ZoneState()
        result = _default_update(
            original,
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
        )
        assert original.waiting_bull is False
        assert result.waiting_bull is True


# ---------------------------------------------------------------------------
# update_zone — invalidation
# ---------------------------------------------------------------------------


class TestZoneInvalidation:
    def _armed_bull(self) -> ZoneState:
        return _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            current_close="105",  # neutral — above SL
        )

    def _armed_bear(self) -> ZoneState:
        return _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            current_close="105",  # neutral — below SL
        )

    def test_bull_zone_invalidated_when_close_below_sl(self) -> None:
        s = self._armed_bull()
        assert s.waiting_bull is True
        # Close below bull_sl (which is just under 100)
        s2 = _default_update(s, current_close="98")
        assert s2.waiting_bull is False

    def test_bull_zone_survives_when_close_above_sl(self) -> None:
        s = self._armed_bull()
        s2 = _default_update(s, current_close="101")
        assert s2.waiting_bull is True

    def test_bear_zone_invalidated_when_close_above_sl(self) -> None:
        s = self._armed_bear()
        assert s.waiting_bear is True
        # Close above bear_sl (which is just above 110)
        s2 = _default_update(s, current_close="115")
        assert s2.waiting_bear is False

    def test_bear_zone_survives_when_close_below_sl(self) -> None:
        s = self._armed_bear()
        s2 = _default_update(s, current_close="109")
        assert s2.waiting_bear is True

    def test_invalidation_disabled_zone_survives_close_through_sl(self) -> None:
        config = StrategyConfig(invalidate_on_close=False)
        s = _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            config=config,
        )
        # Even with close well below SL, zone must survive
        s2 = _default_update(s, current_close="80", config=config)
        assert s2.waiting_bull is True


# ---------------------------------------------------------------------------
# check_tap
# ---------------------------------------------------------------------------


class TestCheckTap:
    def _bull_state(self, config: StrategyConfig | None = None) -> ZoneState:
        return _default_update(
            ZoneState(),
            bos_up=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            current_close="105",
            config=config or StrategyConfig(),
        )

    def _bear_state(self, config: StrategyConfig | None = None) -> ZoneState:
        return _default_update(
            ZoneState(),
            bos_down=True,
            swing_high=Decimal("110"),
            swing_low=Decimal("100"),
            current_close="105",
            config=config or StrategyConfig(),
        )

    def test_no_zone_armed_returns_false_false(self) -> None:
        assert check_tap(ZoneState(), _bar("105"), StrategyConfig()) == (False, False)

    def test_bull_tap_fires_when_bar_enters_zone(self) -> None:
        """Bar's low <= ote_top AND bar's high >= ote_bottom."""
        s = self._bull_state()
        # ote_top ≈ 103.82, ote_bottom ≈ 102.10
        # A bar that dips into the zone: low=103.0, high=104.5
        tap_bar = _bar("103.5", high="104.5", low="103.0")
        confirm_bull, confirm_bear = check_tap(s, tap_bar, StrategyConfig())
        assert confirm_bull is True
        assert confirm_bear is False

    def test_bull_tap_does_not_fire_when_bar_above_zone(self) -> None:
        s = self._bull_state()
        # Bar entirely above ote_top (≈103.82): low=104, high=106
        bar = _bar("105", high="106", low="104")
        confirm_bull, _ = check_tap(s, bar, StrategyConfig())
        assert confirm_bull is False

    def test_bull_tap_does_not_fire_when_bar_below_zone(self) -> None:
        s = self._bull_state()
        # Bar entirely below ote_bottom (≈102.10): low=100, high=101
        bar = _bar("100.5", high="101", low="100")
        confirm_bull, _ = check_tap(s, bar, StrategyConfig())
        assert confirm_bull is False

    def test_bear_tap_fires_when_bar_enters_zone(self) -> None:
        """Bar's high >= ote_bottom AND bar's low <= ote_top."""
        s = self._bear_state()
        # ote_bottom ≈ 106.18, ote_top ≈ 107.90
        # Bar that rises into the zone: low=106.0, high=107.0
        tap_bar = _bar("106.5", high="107.0", low="106.0")
        confirm_bull, confirm_bear = check_tap(s, tap_bar, StrategyConfig())
        assert confirm_bear is True
        assert confirm_bull is False

    def test_require_close_back_bull_rejects_close_below_ote_bottom(self) -> None:
        """With requireCloseBack=True, close must be >= ote_bottom to confirm."""
        config = StrategyConfig(require_close_back=True)
        s = self._bull_state(config)
        # ote_bottom ≈ 102.10 — close at 101.5 is below it
        bar = _bar("101.5", high="104.0", low="101.0")
        confirm_bull, _ = check_tap(s, bar, config)
        assert confirm_bull is False

    def test_require_close_back_bull_accepts_close_at_ote_bottom(self) -> None:
        config = StrategyConfig(require_close_back=True)
        s = self._bull_state(config)
        ote_bottom = s.bull_ote_bottom
        assert ote_bottom is not None
        # Close exactly at ote_bottom satisfies >=
        bar = _bar(
            str(ote_bottom),
            high=str(ote_bottom + Decimal("2")),
            low=str(ote_bottom - Decimal("0.5")),
        )
        confirm_bull, _ = check_tap(s, bar, config)
        assert confirm_bull is True

    def test_require_close_back_bear_rejects_close_above_ote_top(self) -> None:
        config = StrategyConfig(require_close_back=True)
        s = self._bear_state(config)
        # ote_top ≈ 107.90 — close at 108.5 is above it
        bar = _bar("108.5", high="109.0", low="106.5")
        _, confirm_bear = check_tap(s, bar, config)
        assert confirm_bear is False

    def test_require_close_back_false_does_not_need_close_inside(self) -> None:
        """requireCloseBack=False: tap fires on wick entry regardless of close."""
        config = StrategyConfig(require_close_back=False)
        s = self._bull_state(config)
        # Close above OTE zone — but wick dips into it
        ote_top = s.bull_ote_top
        assert ote_top is not None
        bar = _bar(
            str(ote_top + Decimal("1")),
            high=str(ote_top + Decimal("2")),
            low=str(ote_top - Decimal("0.5")),
        )
        confirm_bull, _ = check_tap(s, bar, config)
        assert confirm_bull is True

    def test_not_waiting_zone_does_not_fire(self) -> None:
        """If waiting_bull is False the tap check must not fire even if price is in range."""
        s = self._bull_state()
        s_disarmed = ZoneState(
            waiting_bull=False,
            bull_ote_top=s.bull_ote_top,
            bull_ote_bottom=s.bull_ote_bottom,
        )
        bar = _bar("103.5", high="104.5", low="103.0")
        confirm_bull, _ = check_tap(s_disarmed, bar, StrategyConfig())
        assert confirm_bull is False
