"""Unit tests for the Risk Engine (Task 6).

kScript canonical behavior:
  Bull guard:   entry - sl > 0   (else skip)
  Bear guard:   sl - entry > 0   (else skip)
  Fixed RR TP:  entry ± risk * rr_ratio
  Fib ext TP:   leg_high/low ± leg_range * fib_ext
"""

from decimal import Decimal

import pytest
from app.domain.strategy.ict.risk import calculate_bear_risk, calculate_bull_risk
from app.domain.strategy.models.config import StrategyConfig

D = Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**kwargs: object) -> StrategyConfig:
    return StrategyConfig(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# calculate_bull_risk
# ---------------------------------------------------------------------------


class TestCalculateBullRisk:
    # --- Fixed RR (default) ---

    def test_fixed_rr_basic(self) -> None:
        """entry=100, sl=98, rr=2.0 → tp = 100 + (100-98)*2 = 104."""
        result = calculate_bull_risk(D("100"), D("98"), D("95"), D("110"), _cfg())
        assert result is not None
        assert result.entry == D("100")
        assert result.stop_loss == D("98")
        assert result.take_profit == D("104")
        assert result.risk_reward == D("2.0")

    def test_fixed_rr_rr_ratio_three(self) -> None:
        result = calculate_bull_risk(D("100"), D("98"), D("95"), D("110"), _cfg(rr_ratio=D("3.0")))
        assert result is not None
        assert result.take_profit == D("106")
        assert result.risk_reward == D("3.0")

    def test_fixed_rr_crypto_prices(self) -> None:
        """Realistic BTC-scale numbers."""
        result = calculate_bull_risk(D("64000"), D("63500"), D("63000"), D("65000"), _cfg())
        assert result is not None
        assert result.take_profit == D("65000")
        assert result.risk_reward == D("2.0")

    # --- Fib Extension ---

    def test_fib_ext_tp(self) -> None:
        """entry=105, sl=100, leg_low=95, leg_high=110, fib_ext=1.0
        tp = 110 + (110-95)*1.0 = 110 + 15 = 125
        """
        config = _cfg(tp_mode="Fib Extension", fib_ext=D("1.0"))
        result = calculate_bull_risk(D("105"), D("100"), D("95"), D("110"), config)
        assert result is not None
        assert result.take_profit == D("125")

    def test_fib_ext_half(self) -> None:
        """fib_ext=0.5: tp = 110 + (110-95)*0.5 = 110 + 7.5 = 117.5"""
        config = _cfg(tp_mode="Fib Extension", fib_ext=D("0.5"))
        result = calculate_bull_risk(D("105"), D("100"), D("95"), D("110"), config)
        assert result is not None
        assert result.take_profit == D("117.5")

    # --- Risk guards ---

    def test_guard_inverted_risk_returns_none(self) -> None:
        """entry <= sl (inverted) → must return None."""
        assert calculate_bull_risk(D("98"), D("100"), D("90"), D("110"), _cfg()) is None

    def test_guard_zero_risk_returns_none(self) -> None:
        """entry == sl → risk = 0 → must return None."""
        assert calculate_bull_risk(D("100"), D("100"), D("90"), D("110"), _cfg()) is None

    def test_guard_barely_positive_returns_result(self) -> None:
        """Any positive risk, no matter how small, must produce a result."""
        result = calculate_bull_risk(D("100.01"), D("100"), D("90"), D("110"), _cfg())
        assert result is not None

    # --- RiskLevels structure ---

    def test_risk_reward_is_derived_correctly(self) -> None:
        """risk_reward = abs(tp - entry) / abs(entry - sl)"""
        result = calculate_bull_risk(D("100"), D("97"), D("90"), D("110"), _cfg(rr_ratio=D("3.0")))
        assert result is not None
        expected_rr = abs(result.take_profit - result.entry) / abs(result.entry - result.stop_loss)
        assert result.risk_reward == expected_rr

    def test_result_is_frozen(self) -> None:
        result = calculate_bull_risk(D("100"), D("98"), D("90"), D("110"), _cfg())
        assert result is not None
        try:
            result.entry = D("999")  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# calculate_bear_risk
# ---------------------------------------------------------------------------


class TestCalculateBearRisk:
    # --- Fixed RR (default) ---

    def test_fixed_rr_basic(self) -> None:
        """entry=100, sl=102, rr=2.0 → tp = 100 - (102-100)*2 = 96."""
        result = calculate_bear_risk(D("100"), D("102"), D("90"), D("110"), _cfg())
        assert result is not None
        assert result.entry == D("100")
        assert result.stop_loss == D("102")
        assert result.take_profit == D("96")
        assert result.risk_reward == D("2.0")

    def test_fixed_rr_rr_ratio_three(self) -> None:
        result = calculate_bear_risk(D("100"), D("102"), D("90"), D("110"), _cfg(rr_ratio=D("3.0")))
        assert result is not None
        assert result.take_profit == D("94")
        assert result.risk_reward == D("3.0")

    def test_fixed_rr_crypto_prices(self) -> None:
        result = calculate_bear_risk(D("64000"), D("64500"), D("63000"), D("65000"), _cfg())
        assert result is not None
        assert result.take_profit == D("63000")
        assert result.risk_reward == D("2.0")

    # --- Fib Extension ---

    def test_fib_ext_tp(self) -> None:
        """entry=105, sl=110, leg_low=95, leg_high=110, fib_ext=1.0
        tp = 95 - (110-95)*1.0 = 95 - 15 = 80
        """
        config = _cfg(tp_mode="Fib Extension", fib_ext=D("1.0"))
        result = calculate_bear_risk(D("105"), D("110"), D("95"), D("110"), config)
        assert result is not None
        assert result.take_profit == D("80")

    def test_fib_ext_half(self) -> None:
        """fib_ext=0.5: tp = 95 - (110-95)*0.5 = 95 - 7.5 = 87.5"""
        config = _cfg(tp_mode="Fib Extension", fib_ext=D("0.5"))
        result = calculate_bear_risk(D("105"), D("110"), D("95"), D("110"), config)
        assert result is not None
        assert result.take_profit == D("87.5")

    # --- Risk guards ---

    def test_guard_inverted_risk_returns_none(self) -> None:
        """sl <= entry (inverted for bear) → must return None."""
        assert calculate_bear_risk(D("102"), D("100"), D("90"), D("110"), _cfg()) is None

    def test_guard_zero_risk_returns_none(self) -> None:
        """sl == entry → risk = 0 → must return None."""
        assert calculate_bear_risk(D("100"), D("100"), D("90"), D("110"), _cfg()) is None

    def test_guard_barely_positive_returns_result(self) -> None:
        result = calculate_bear_risk(D("100"), D("100.01"), D("90"), D("110"), _cfg())
        assert result is not None

    # --- RiskLevels structure ---

    def test_risk_reward_is_derived_correctly(self) -> None:
        result = calculate_bear_risk(D("100"), D("103"), D("90"), D("110"), _cfg(rr_ratio=D("3.0")))
        assert result is not None
        expected_rr = abs(result.entry - result.take_profit) / abs(result.stop_loss - result.entry)
        assert result.risk_reward == expected_rr

    # --- Symmetry between bull and bear ---

    @pytest.mark.parametrize("rr", ["1.0", "2.0", "3.0", "5.0"])
    def test_bull_and_bear_produce_symmetric_rr(self, rr: str) -> None:
        """Both directions with the same RR ratio produce identical risk_reward values."""
        config = _cfg(rr_ratio=D(rr))
        bull = calculate_bull_risk(D("100"), D("98"), D("90"), D("110"), config)
        bear = calculate_bear_risk(D("100"), D("102"), D("90"), D("110"), config)
        assert bull is not None
        assert bear is not None
        assert bull.risk_reward == bear.risk_reward == D(rr)
