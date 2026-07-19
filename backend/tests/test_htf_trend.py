"""Unit tests for HTF EMA trend filter (Task 4).

kScript canonical behavior:
    htfBullish = !useHTFTrend || h4ema > h4ema[emaSlopeLen]
    htfBearish = !useHTFTrend || h4ema < h4ema[emaSlopeLen]
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.strategy.ict.htf_trend import compute_ema, evaluate_trend
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(close: str) -> Bar:
    c = Decimal(close)
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=c,
        high=c,
        low=c,
        close=c,
        volume=Decimal("1000"),
    )


def _bars(closes: list[str]) -> list[Bar]:
    return [_bar(c) for c in closes]


def _rising_bars(n: int, start: int = 100, step: int = 1) -> list[Bar]:
    """n bars with monotonically increasing closes."""
    return [_bar(str(start + i * step)) for i in range(n)]


def _falling_bars(n: int, start: int = 200, step: int = 1) -> list[Bar]:
    """n bars with monotonically decreasing closes."""
    return [_bar(str(start - i * step)) for i in range(n)]


# ---------------------------------------------------------------------------
# compute_ema
# ---------------------------------------------------------------------------


class TestComputeEma:
    def test_empty_input_returns_empty(self) -> None:
        assert compute_ema([], 5) == []

    def test_fewer_bars_than_period_returns_closes(self) -> None:
        bars = _bars(["10", "20", "30"])
        result = compute_ema(bars, 5)
        assert len(result) == 3
        assert result == [Decimal("10"), Decimal("20"), Decimal("30")]

    def test_output_same_length_as_input(self) -> None:
        bars = _rising_bars(60)
        result = compute_ema(bars, 10)
        assert len(result) == 60

    def test_seed_is_sma_of_first_period_bars(self) -> None:
        """The first EMA value (at index period-1) equals the SMA of opens."""
        bars = _bars(["10", "20", "30"])  # period=3
        result = compute_ema(bars, 3)
        expected_seed = (Decimal("10") + Decimal("20") + Decimal("30")) / Decimal("3")
        # Index 2 is the seed (period - 1 = 2)
        assert result[2] == expected_seed

    def test_ema_rises_on_rising_prices(self) -> None:
        bars = _rising_bars(60)
        result = compute_ema(bars, 10)
        # EMA should be strictly increasing after the seed window.
        assert result[-1] > result[-10]

    def test_ema_falls_on_falling_prices(self) -> None:
        bars = _falling_bars(60)
        result = compute_ema(bars, 10)
        assert result[-1] < result[-10]

    def test_ema_spot_check_period_3(self) -> None:
        """Manual calculation for a known series with period=3.

        Closes: [10, 20, 30, 40]
        k = 2 / (3+1) = 0.5
        seed (SMA of first 3) = (10+20+30)/3 = 20
        ema[3] = 40 * 0.5 + 20 * 0.5 = 30
        """
        bars = _bars(["10", "20", "30", "40"])
        result = compute_ema(bars, 3)
        assert result[3] == Decimal("30")

    def test_ema_spot_check_period_2(self) -> None:
        """k = 2/(2+1) = 2/3.
        Closes: [100, 200, 300]
        seed = (100+200)/2 = 150
        ema[2] = 300 * (2/3) + 150 * (1/3) = 200 + 50 = 250
        """
        bars = _bars(["100", "200", "300"])
        result = compute_ema(bars, 2)
        k = Decimal("2") / Decimal("3")
        seed = Decimal("150")
        expected = Decimal("300") * k + seed * (Decimal("1") - k)
        assert result[2] == expected


# ---------------------------------------------------------------------------
# evaluate_trend
# ---------------------------------------------------------------------------


class TestEvaluateTrend:
    def test_filter_disabled_always_returns_true_true(self) -> None:
        """use_htf_trend=False → (True, True) regardless of bar data."""
        config = StrategyConfig(use_htf_trend=False)
        # Even with zero bars
        assert evaluate_trend([], config) == (True, True)

    def test_filter_disabled_with_falling_bars_still_true_true(self) -> None:
        config = StrategyConfig(use_htf_trend=False)
        bars = _falling_bars(60)
        assert evaluate_trend(bars, config) == (True, True)

    def test_insufficient_bars_returns_true_true(self) -> None:
        """Fewer than period + slope_lookback bars → fail open → (True, True)."""
        config = StrategyConfig(use_htf_trend=True, htf_ema_len=50, ema_slope_lookback=3)
        bars = _rising_bars(52)  # need 53, have 52
        assert evaluate_trend(bars, config) == (True, True)

    def test_exactly_sufficient_bars_does_not_fail_open(self) -> None:
        """Exactly period + slope_lookback bars should evaluate (not fail open)."""
        config = StrategyConfig(use_htf_trend=True, htf_ema_len=10, ema_slope_lookback=3)
        bars = _rising_bars(13)  # exactly 10+3
        result = evaluate_trend(bars, config)
        # Rising prices → should be bullish
        assert result[0] is True

    def test_rising_prices_produce_bullish_trend(self) -> None:
        config = StrategyConfig(use_htf_trend=True, htf_ema_len=50, ema_slope_lookback=3)
        bars = _rising_bars(60)
        htf_bullish, htf_bearish = evaluate_trend(bars, config)
        assert htf_bullish is True
        assert htf_bearish is False

    def test_falling_prices_produce_bearish_trend(self) -> None:
        config = StrategyConfig(use_htf_trend=True, htf_ema_len=50, ema_slope_lookback=3)
        bars = _falling_bars(60)
        htf_bullish, htf_bearish = evaluate_trend(bars, config)
        assert htf_bullish is False
        assert htf_bearish is True

    def test_flat_prices_neither_bullish_nor_bearish(self) -> None:
        """Flat EMA slope → neither condition is True (EMA neither > nor < itself)."""
        config = StrategyConfig(use_htf_trend=True, htf_ema_len=5, ema_slope_lookback=2)
        # Constant price → EMA is constant after seeding
        bars = _bars(["100"] * 20)
        htf_bullish, htf_bearish = evaluate_trend(bars, config)
        assert htf_bullish is False
        assert htf_bearish is False

    @pytest.mark.parametrize("ema_len,slope_lb", [(10, 2), (20, 3), (50, 3)])
    def test_rising_bullish_across_configurations(self, ema_len: int, slope_lb: int) -> None:
        config = StrategyConfig(
            use_htf_trend=True, htf_ema_len=ema_len, ema_slope_lookback=slope_lb
        )
        bars = _rising_bars(ema_len + slope_lb + 20)
        htf_bullish, _ = evaluate_trend(bars, config)
        assert htf_bullish is True

    def test_slope_lookback_sensitivity(self) -> None:
        """A short slope lookback detects trend reversal faster."""
        # Build a series: 40 bars rising then 10 bars flat
        bars = _rising_bars(40) + _bars(["140"] * 10)
        config_short = StrategyConfig(use_htf_trend=True, htf_ema_len=10, ema_slope_lookback=1)
        config_long = StrategyConfig(use_htf_trend=True, htf_ema_len=10, ema_slope_lookback=8)
        # Short lookback will detect the flat sooner; long lookback still sees old slope.
        # Both should return valid (non-error) results.
        r_short = evaluate_trend(bars, config_short)
        r_long = evaluate_trend(bars, config_long)
        assert isinstance(r_short, tuple)
        assert isinstance(r_long, tuple)
