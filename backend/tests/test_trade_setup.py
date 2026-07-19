"""Unit tests for the TradeSetup domain object (Task 7)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup

D = Decimal


def _valid_setup(**overrides: object) -> TradeSetup:
    defaults: dict[str, object] = dict(
        symbol="BTC",
        direction="long",
        entry=D("64000"),
        stop_loss=D("63500"),
        take_profit=D("65000"),
        risk_reward=D("2.0"),
        timeframe="15m",
        reasons=["Bullish BOS confirmed"],
        warnings=[],
        swing_high=D("65000"),
        swing_low=D("63000"),
        ote_top=D("63820"),
        ote_bottom=D("63580"),
        leg_low=D("63000"),
        leg_high=D("65000"),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        config_snapshot=StrategyConfig(),
    )
    defaults.update(overrides)
    return TradeSetup(**defaults)  # type: ignore[arg-type]


class TestTradeSetup:
    def test_valid_long_setup_constructs(self) -> None:
        setup = _valid_setup()
        assert setup.direction == "long"
        assert setup.symbol == "BTC"
        assert setup.strategy == "ICT Pure OTE"

    def test_valid_short_setup_constructs(self) -> None:
        setup = _valid_setup(
            direction="short",
            entry=D("64000"),
            stop_loss=D("64500"),
            take_profit=D("63000"),
        )
        assert setup.direction == "short"

    def test_strategy_field_defaults_to_ict(self) -> None:
        assert _valid_setup().strategy == "ICT Pure OTE"

    def test_timeframe_can_be_none(self) -> None:
        setup = _valid_setup(timeframe=None)
        assert setup.timeframe is None

    def test_warnings_can_be_empty(self) -> None:
        setup = _valid_setup(warnings=[])
        assert setup.warnings == []

    def test_swing_high_low_can_be_none(self) -> None:
        setup = _valid_setup(swing_high=None, swing_low=None)
        assert setup.swing_high is None
        assert setup.swing_low is None

    def test_config_snapshot_is_stored(self) -> None:
        cfg = StrategyConfig(rr_ratio=D("3.0"), swing_len=10)
        setup = _valid_setup(config_snapshot=cfg)
        assert setup.config_snapshot.rr_ratio == D("3.0")
        assert setup.config_snapshot.swing_len == 10

    def test_direction_validates_only_long_or_short(self) -> None:
        with pytest.raises(ValueError):
            _valid_setup(direction="both")  # type: ignore[arg-type]

    def test_reasons_must_be_list(self) -> None:
        """Reasons is always a list — never a plain string."""
        setup = _valid_setup(reasons=["reason one", "reason two"])
        assert isinstance(setup.reasons, list)
        assert len(setup.reasons) == 2

    def test_all_decimal_fields_preserved(self) -> None:
        setup = _valid_setup()
        assert isinstance(setup.entry, Decimal)
        assert isinstance(setup.stop_loss, Decimal)
        assert isinstance(setup.take_profit, Decimal)
        assert isinstance(setup.risk_reward, Decimal)
        assert isinstance(setup.ote_top, Decimal)
        assert isinstance(setup.ote_bottom, Decimal)
        assert isinstance(setup.leg_low, Decimal)
        assert isinstance(setup.leg_high, Decimal)

    def test_timestamp_is_datetime(self) -> None:
        setup = _valid_setup()
        assert isinstance(setup.timestamp, datetime)
