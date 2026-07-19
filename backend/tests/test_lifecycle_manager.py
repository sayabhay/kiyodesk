"""Tests for LifecycleManager status transitions (Task 4)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity
from app.runtime.lifecycle_manager import InvalidTransitionError, LifecycleManager

D = Decimal


def _opp(status: str = OpportunityStatus.ACTIVE, **overrides: object) -> TradeOpportunity:
    defaults: dict[str, object] = dict(
        strategy="ICT Pure OTE",
        symbol="BTC",
        direction="long",
        entry=D("64000"),
        stop_loss=D("63500"),
        take_profit=D("65000"),
        risk_reward=D("2.0"),
        status=status,
        trade_setup_json="{}",
        entry_tolerance=D("1"),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    defaults.update(overrides)
    return TradeOpportunity(**defaults)  # type: ignore[arg-type]


class TestAccept:
    def test_active_to_taken(self) -> None:
        lm = LifecycleManager()
        opp = _opp(OpportunityStatus.ACTIVE)
        result = lm.accept(opp, trade_id=5)
        assert result.status == OpportunityStatus.TAKEN
        assert result.trade_id == 5
        assert result.taken_at is not None

    def test_taken_at_is_set(self) -> None:
        before = datetime.now(tz=UTC)
        opp = _opp()
        LifecycleManager().accept(opp, trade_id=1)
        assert opp.taken_at is not None
        assert opp.taken_at >= before

    def test_non_active_raises(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc:
            LifecycleManager().accept(_opp(OpportunityStatus.REJECTED), trade_id=1)
        assert exc.value.current == "rejected"
        assert exc.value.target == "taken"

    def test_already_taken_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().accept(_opp(OpportunityStatus.TAKEN), trade_id=2)

    def test_zero_trade_id_raises(self) -> None:
        with pytest.raises(ValueError):
            LifecycleManager().accept(_opp(), trade_id=0)

    def test_negative_trade_id_raises(self) -> None:
        with pytest.raises(ValueError):
            LifecycleManager().accept(_opp(), trade_id=-1)

    def test_returns_same_object(self) -> None:
        opp = _opp()
        result = LifecycleManager().accept(opp, trade_id=3)
        assert result is opp


class TestReject:
    def test_active_to_rejected(self) -> None:
        opp = _opp()
        LifecycleManager().reject(opp)
        assert opp.status == OpportunityStatus.REJECTED

    def test_non_active_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().reject(_opp(OpportunityStatus.TAKEN))

    def test_expired_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().reject(_opp(OpportunityStatus.EXPIRED))

    def test_no_trade_created(self) -> None:
        opp = _opp()
        LifecycleManager().reject(opp)
        assert opp.trade_id is None


class TestInvalidate:
    def test_active_to_invalidated(self) -> None:
        opp = _opp()
        LifecycleManager().invalidate(opp)
        assert opp.status == OpportunityStatus.INVALIDATED
        assert opp.invalidated_at is not None

    def test_non_active_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().invalidate(_opp(OpportunityStatus.REJECTED))

    def test_invalidated_at_set(self) -> None:
        before = datetime.now(tz=UTC)
        opp = _opp()
        LifecycleManager().invalidate(opp)
        assert opp.invalidated_at >= before


class TestExpire:
    def test_active_to_expired(self) -> None:
        opp = _opp()
        LifecycleManager().expire(opp)
        assert opp.status == OpportunityStatus.EXPIRED

    def test_non_active_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().expire(_opp(OpportunityStatus.TAKEN))


class TestComplete:
    def test_taken_to_completed(self) -> None:
        opp = _opp(OpportunityStatus.TAKEN, trade_id=7)
        LifecycleManager().complete(opp)
        assert opp.status == OpportunityStatus.COMPLETED

    def test_active_raises(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc:
            LifecycleManager().complete(_opp(OpportunityStatus.ACTIVE))
        assert exc.value.current == "active"
        assert exc.value.target == "completed"

    def test_rejected_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            LifecycleManager().complete(_opp(OpportunityStatus.REJECTED))


class TestInvalidTransitionError:
    def test_message_includes_statuses(self) -> None:
        err = InvalidTransitionError("active", "completed")
        assert "active" in str(err)
        assert "completed" in str(err)

    def test_attributes(self) -> None:
        err = InvalidTransitionError("rejected", "taken")
        assert err.current == "rejected"
        assert err.target == "taken"
