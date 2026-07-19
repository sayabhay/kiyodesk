"""Tests for TradeOpportunity model and OpportunityStatus enum (Task 1)."""

from decimal import Decimal

from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity


def _opp(**overrides: object) -> TradeOpportunity:
    defaults: dict[str, object] = dict(
        strategy="ICT Pure OTE",
        symbol="BTC",
        direction="long",
        entry=Decimal("64000"),
        stop_loss=Decimal("63500"),
        take_profit=Decimal("65000"),
        risk_reward=Decimal("2.0"),
        trade_setup_json='{"symbol":"BTC"}',
    )
    defaults.update(overrides)
    return TradeOpportunity(**defaults)  # type: ignore[arg-type]


class TestOpportunityStatus:
    def test_all_statuses_defined(self) -> None:
        statuses = {s.value for s in OpportunityStatus}
        expected = {"new", "active", "taken", "rejected", "invalidated", "expired", "completed"}
        assert statuses == expected

    def test_status_is_string(self) -> None:
        assert OpportunityStatus.ACTIVE == "active"
        assert isinstance(OpportunityStatus.TAKEN, str)


class TestTradeOpportunityModel:
    def test_constructs_with_required_fields(self) -> None:
        opp = _opp()
        assert opp.strategy == "ICT Pure OTE"
        assert opp.symbol == "BTC"
        assert opp.direction == "long"
        assert opp.entry == Decimal("64000")
        assert opp.stop_loss == Decimal("63500")
        assert opp.take_profit == Decimal("65000")
        assert opp.risk_reward == Decimal("2.0")

    def test_nullable_fields_default_to_none(self) -> None:
        opp = _opp()
        assert opp.trade_id is None
        assert opp.confidence is None
        assert opp.market_regime is None
        assert opp.expires_at is None
        assert opp.taken_at is None
        assert opp.invalidated_at is None
        assert opp.metadata_json is None
        assert opp.strategy_version is None
        assert opp.timeframe is None

    def test_trade_setup_json_stored(self) -> None:
        opp = _opp(trade_setup_json='{"symbol":"BTC","direction":"long"}')
        assert opp.trade_setup_json == '{"symbol":"BTC","direction":"long"}'

    def test_confidence_and_regime_placeholders(self) -> None:
        """confidence and market_regime are null until v0.6 / v0.7."""
        opp = _opp()
        assert opp.confidence is None
        assert opp.market_regime is None

    def test_custom_status_accepted(self) -> None:
        opp = _opp(status=OpportunityStatus.TAKEN)
        assert opp.status == "taken"
