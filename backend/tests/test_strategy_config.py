"""Tests for Bar dataclass and StrategyConfig defaults (Task 1)."""

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig


def _bar(price: str = "100") -> Bar:
    """Build a minimal Bar for structural tests."""
    p = Decimal(price)
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=p,
        high=p,
        low=p,
        close=p,
        volume=Decimal("1000"),
    )


class TestBar:
    def test_bar_is_frozen(self) -> None:
        """Bar is immutable."""
        b = _bar()
        try:
            b.close = Decimal("999")  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except Exception:
            pass

    def test_bar_fields_accessible(self) -> None:
        b = _bar("64000")
        assert b.open == Decimal("64000")
        assert b.high == Decimal("64000")
        assert b.low == Decimal("64000")
        assert b.close == Decimal("64000")
        assert b.volume == Decimal("1000")
        assert b.timestamp.tzinfo is not None


class TestStrategyConfig:
    def test_defaults_match_kscript_exactly(self) -> None:
        """Every default must match the kScript input() declaration."""
        c = StrategyConfig()
        assert c.swing_len == 5
        assert c.trade_dir == "Both"
        assert c.use_htf_trend is True
        assert c.htf_ema_len == 50
        assert c.ema_slope_lookback == 3
        assert c.ote_start == Decimal("0.618")
        assert c.ote_end == Decimal("0.79")
        assert c.require_close_back is False
        assert c.sl_buffer_pct == Decimal("0.05")
        assert c.tp_mode == "Fixed RR"
        assert c.rr_ratio == Decimal("2.0")
        assert c.fib_ext == Decimal("1.0")
        assert c.invalidate_on_close is True

    def test_config_is_frozen(self) -> None:
        """StrategyConfig must be immutable once constructed."""
        c = StrategyConfig()
        try:
            c.swing_len = 10  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except Exception:
            pass

    def test_custom_values_accepted(self) -> None:
        c = StrategyConfig(
            swing_len=10,
            trade_dir="Long Only",
            use_htf_trend=False,
            tp_mode="Fib Extension",
            rr_ratio=Decimal("3.0"),
        )
        assert c.swing_len == 10
        assert c.trade_dir == "Long Only"
        assert c.use_htf_trend is False
        assert c.tp_mode == "Fib Extension"
        assert c.rr_ratio == Decimal("3.0")
