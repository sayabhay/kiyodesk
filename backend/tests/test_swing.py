"""Unit tests for swing pivot detection (Task 2).

kScript canonical behavior:
  pivothigh(leftbars=swingLen, rightbars=swingLen) — strict pivot high
  pivotlow(leftbars=swingLen, rightbars=swingLen)  — strict pivot low
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.strategy.ict.swing import detect_pivots
from app.domain.strategy.interfaces.bar import Bar


def _bar(high: str, low: str, close: str | None = None) -> Bar:
    """Build a Bar with the given high/low; close defaults to midpoint."""
    h = Decimal(high)
    lo = Decimal(low)
    c = Decimal(close) if close else (h + lo) / 2
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=c,
        high=h,
        low=lo,
        close=c,
        volume=Decimal("1000"),
    )


def _flat_bars(n: int, price: str = "100") -> list[Bar]:
    """Return n identical bars at the given price."""
    return [_bar(price, price) for _ in range(n)]


class TestDetectPivots:
    def test_empty_series_returns_none_none(self) -> None:
        assert detect_pivots([], 5) == (None, None)

    def test_too_short_returns_none_none(self) -> None:
        """Fewer than 2*swing_len+1 bars cannot have a confirmed pivot."""
        bars = _flat_bars(9)  # need 11 for swing_len=5
        assert detect_pivots(bars, 5) == (None, None)

    def test_minimum_length_exact(self) -> None:
        """Exactly 2*swing_len+1 bars — the single candidate is bar[swing_len]."""
        swing_len = 3
        bars = _flat_bars(2 * swing_len + 1, "100")
        # All equal — no strict pivot
        assert detect_pivots(bars, swing_len) == (None, None)

    def test_flat_series_returns_none_none(self) -> None:
        """No strict pivots in a flat series (ties are not pivots)."""
        bars = _flat_bars(20)
        assert detect_pivots(bars, 5) == (None, None)

    def test_spike_high_detected(self) -> None:
        """A single spike bar produces a confirmed pivot high."""
        swing_len = 3
        bars = _flat_bars(20, "100")
        # Plant spike at index 7 — it has 3 bars on each side within window,
        # and swing_len bars still exist to its right (indices 8..10 minimum).
        bars[7] = _bar("200", "100")
        ph, pl = detect_pivots(bars, swing_len)
        assert ph == Decimal("200")

    def test_spike_low_detected(self) -> None:
        """A single dip bar produces a confirmed pivot low."""
        swing_len = 3
        bars = _flat_bars(20, "100")
        bars[7] = _bar("100", "10")
        ph, pl = detect_pivots(bars, swing_len)
        assert pl == Decimal("10")

    def test_most_recent_pivot_returned(self) -> None:
        """When multiple pivots exist the most recent confirmed one is returned."""
        swing_len = 3
        bars = _flat_bars(25, "100")
        bars[5] = _bar("300", "100")  # older pivot high
        bars[15] = _bar("400", "100")  # newer pivot high
        ph, _ = detect_pivots(bars, swing_len)
        assert ph == Decimal("400")

    def test_tie_is_not_a_pivot(self) -> None:
        """Two bars sharing the highest high — neither is a strict pivot."""
        swing_len = 3
        bars = _flat_bars(20, "100")
        bars[6] = _bar("200", "100")
        bars[7] = _bar("200", "100")  # tie at same high value
        ph, _ = detect_pivots(bars, swing_len)
        # Neither bar 6 nor bar 7 is a strict pivot (bar 7's window contains bar 6 at equal high)
        # bar 6's window contains bar 7 at equal high — no strict pivot
        assert ph is None

    def test_pivot_not_confirmable_in_last_swing_len_bars(self) -> None:
        """A spike in the last swing_len bars cannot be confirmed yet."""
        swing_len = 3
        bars = _flat_bars(20, "100")
        # Place spike at index 18 — only 1 bar to its right, needs 3
        bars[18] = _bar("500", "100")
        ph, _ = detect_pivots(bars, swing_len)
        assert ph is None

    def test_swing_high_and_low_both_detected(self) -> None:
        """Both pivot high and low can be detected independently."""
        swing_len = 2
        bars = _flat_bars(20, "100")
        bars[5] = _bar("200", "100")  # pivot high
        bars[12] = _bar("100", "10")  # pivot low
        ph, pl = detect_pivots(bars, swing_len)
        assert ph == Decimal("200")
        assert pl == Decimal("10")

    def test_spike_at_index_swing_len_is_valid_candidate(self) -> None:
        """The earliest valid candidate is index swing_len itself."""
        swing_len = 3
        bars = _flat_bars(20, "100")
        bars[swing_len] = _bar("999", "100")
        ph, _ = detect_pivots(bars, swing_len)
        assert ph == Decimal("999")

    @pytest.mark.parametrize("swing_len", [2, 3, 5, 8])
    def test_various_swing_lengths(self, swing_len: int) -> None:
        """Pivot detection works correctly across the allowed swing_len range."""
        n = swing_len * 4 + 1
        bars = _flat_bars(n, "100")
        spike_idx = swing_len + 1
        bars[spike_idx] = _bar("999", "100")
        ph, _ = detect_pivots(bars, swing_len)
        assert ph == Decimal("999")
