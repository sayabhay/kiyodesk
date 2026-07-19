"""Unit tests for Break of Structure detection (Task 3).

kScript canonical behavior:
    bosUp   = !isna(swingHigh) && bars.close > swingHigh && bars.close[1] <= swingHigh
    bosDown = !isna(swingLow)  && bars.close < swingLow  && bars.close[1] >= swingLow
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.strategy.ict.bos import detect_bos
from app.domain.strategy.interfaces.bar import Bar


def _bar(close: str, high: str | None = None, low: str | None = None) -> Bar:
    """Build a minimal Bar with the given close (high/low default to close)."""
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


def _bars(closes: list[str]) -> list[Bar]:
    """Build a bar series from a list of close price strings."""
    return [_bar(c) for c in closes]


class TestDetectBos:
    # ------------------------------------------------------------------
    # Guard conditions
    # ------------------------------------------------------------------

    def test_empty_bars_returns_false_false(self) -> None:
        assert detect_bos([], None, None) == (False, False)

    def test_single_bar_returns_false_false(self) -> None:
        assert detect_bos([_bar("100")], Decimal("100"), Decimal("100")) == (False, False)

    def test_no_swing_levels_returns_false_false(self) -> None:
        bars = _bars(["99", "101"])
        assert detect_bos(bars, None, None) == (False, False)

    def test_no_swing_high_suppresses_bos_up(self) -> None:
        bars = _bars(["99", "101"])
        bos_up, _ = detect_bos(bars, None, Decimal("50"))
        assert bos_up is False

    def test_no_swing_low_suppresses_bos_down(self) -> None:
        bars = _bars(["101", "99"])
        _, bos_down = detect_bos(bars, Decimal("200"), None)
        assert bos_down is False

    # ------------------------------------------------------------------
    # Bullish BOS
    # ------------------------------------------------------------------

    def test_bullish_bos_clean_crossover(self) -> None:
        """Close crosses above swing_high: prior ≤ level, current > level."""
        bars = _bars(["99", "101"])
        bos_up, bos_down = detect_bos(bars, Decimal("100"), None)
        assert bos_up is True
        assert bos_down is False

    def test_bullish_bos_prior_exactly_at_level(self) -> None:
        """Prior close exactly equal to swing_high still qualifies (≤ condition)."""
        bars = _bars(["100", "101"])
        bos_up, _ = detect_bos(bars, Decimal("100"), None)
        assert bos_up is True

    def test_bullish_bos_no_crossover_already_above(self) -> None:
        """Prior close already above swing_high — not a new crossover."""
        bars = _bars(["102", "105"])
        bos_up, _ = detect_bos(bars, Decimal("100"), None)
        assert bos_up is False

    def test_bullish_bos_current_exactly_at_level_not_above(self) -> None:
        """Current close equal to swing_high does not satisfy strict >."""
        bars = _bars(["99", "100"])
        bos_up, _ = detect_bos(bars, Decimal("100"), None)
        assert bos_up is False

    def test_bullish_bos_current_below_level(self) -> None:
        bars = _bars(["99", "98"])
        bos_up, _ = detect_bos(bars, Decimal("100"), None)
        assert bos_up is False

    # ------------------------------------------------------------------
    # Bearish BOS
    # ------------------------------------------------------------------

    def test_bearish_bos_clean_crossover(self) -> None:
        """Close crosses below swing_low: prior ≥ level, current < level."""
        bars = _bars(["101", "99"])
        bos_up, bos_down = detect_bos(bars, None, Decimal("100"))
        assert bos_down is True
        assert bos_up is False

    def test_bearish_bos_prior_exactly_at_level(self) -> None:
        """Prior close exactly equal to swing_low still qualifies (≥ condition)."""
        bars = _bars(["100", "99"])
        _, bos_down = detect_bos(bars, None, Decimal("100"))
        assert bos_down is True

    def test_bearish_bos_no_crossover_already_below(self) -> None:
        """Prior close already below swing_low — not a new crossover."""
        bars = _bars(["98", "95"])
        _, bos_down = detect_bos(bars, None, Decimal("100"))
        assert bos_down is False

    def test_bearish_bos_current_exactly_at_level_not_below(self) -> None:
        """Current close equal to swing_low does not satisfy strict <."""
        bars = _bars(["101", "100"])
        _, bos_down = detect_bos(bars, None, Decimal("100"))
        assert bos_down is False

    def test_bearish_bos_current_above_level(self) -> None:
        bars = _bars(["101", "102"])
        _, bos_down = detect_bos(bars, None, Decimal("100"))
        assert bos_down is False

    # ------------------------------------------------------------------
    # Mutual exclusivity and boundary conditions
    # ------------------------------------------------------------------

    def test_both_levels_provided_only_bos_up_fires(self) -> None:
        """When crossing above swing_high, bos_down must remain False."""
        bars = _bars(["99", "111"])
        bos_up, bos_down = detect_bos(bars, Decimal("100"), Decimal("50"))
        assert bos_up is True
        assert bos_down is False

    def test_both_levels_provided_only_bos_down_fires(self) -> None:
        """When crossing below swing_low, bos_up must remain False."""
        bars = _bars(["101", "89"])
        bos_up, bos_down = detect_bos(bars, Decimal("200"), Decimal("90"))
        assert bos_up is False
        assert bos_down is True

    def test_neither_fires_when_no_crossover(self) -> None:
        bars = _bars(["100", "100"])
        assert detect_bos(bars, Decimal("110"), Decimal("90")) == (False, False)

    @pytest.mark.parametrize(
        "prior,current,level,expected_up",
        [
            ("99", "101", "100", True),  # standard crossover
            ("100", "101", "100", True),  # prior exactly at level
            ("101", "102", "100", False),  # already above
            ("99", "100", "100", False),  # current exactly at level (not >)
        ],
    )
    def test_bos_up_parametrized(
        self, prior: str, current: str, level: str, expected_up: bool
    ) -> None:
        bars = _bars([prior, current])
        bos_up, _ = detect_bos(bars, Decimal(level), None)
        assert bos_up is expected_up

    @pytest.mark.parametrize(
        "prior,current,level,expected_down",
        [
            ("101", "99", "100", True),  # standard crossover
            ("100", "99", "100", True),  # prior exactly at level
            ("99", "98", "100", False),  # already below
            ("101", "100", "100", False),  # current exactly at level (not <)
        ],
    )
    def test_bos_down_parametrized(
        self, prior: str, current: str, level: str, expected_down: bool
    ) -> None:
        bars = _bars([prior, current])
        _, bos_down = detect_bos(bars, None, Decimal(level))
        assert bos_down is expected_down
