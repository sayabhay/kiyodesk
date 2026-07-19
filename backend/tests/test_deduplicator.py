"""Tests for Deduplicator (Task 3)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup
from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity
from app.runtime.deduplicator import Deduplicator

D = Decimal


def _setup(**overrides: object) -> TradeSetup:
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
        ote_top=D("63820"),
        ote_bottom=D("63580"),
        leg_low=D("63000"),
        leg_high=D("65000"),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        config_snapshot=StrategyConfig(),
    )
    defaults.update(overrides)
    return TradeSetup(**defaults)  # type: ignore[arg-type]


def _opp(**overrides: object) -> TradeOpportunity:
    defaults: dict[str, object] = dict(
        strategy="ICT Pure OTE",
        symbol="BTC",
        direction="long",
        entry=D("64000"),
        stop_loss=D("63500"),
        take_profit=D("65000"),
        risk_reward=D("2.0"),
        timeframe="15m",
        status=OpportunityStatus.ACTIVE,
        trade_setup_json="{}",
        entry_tolerance=D("1"),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    defaults.update(overrides)
    return TradeOpportunity(**defaults)  # type: ignore[arg-type]


class TestDeduplicator:
    def _repo(self, returns: TradeOpportunity | None) -> AsyncMock:
        repo = AsyncMock()
        repo.find_duplicate = AsyncMock(return_value=returns)
        return repo

    async def test_returns_existing_when_match_found(self) -> None:
        existing = _opp()
        repo = self._repo(existing)
        d = Deduplicator(tolerance=D("1"))
        result = await d.find_existing(_setup(), repo)
        assert result is existing

    async def test_returns_none_when_no_match(self) -> None:
        repo = self._repo(None)
        d = Deduplicator(tolerance=D("1"))
        result = await d.find_existing(_setup(), repo)
        assert result is None

    async def test_passes_correct_args_to_repository(self) -> None:
        repo = self._repo(None)
        d = Deduplicator(tolerance=D("0.5"))
        setup = _setup(entry=D("64000"), symbol="BTC", timeframe="15m", direction="long")
        await d.find_existing(setup, repo)
        repo.find_duplicate.assert_called_once_with(
            strategy="ICT Pure OTE",
            symbol="BTC",
            timeframe="15m",
            direction="long",
            entry=D("64000"),
            tolerance=D("0.5"),
        )

    async def test_default_tolerance_is_one_cent(self) -> None:
        d = Deduplicator()
        assert d.tolerance == D("0.01")

    async def test_custom_tolerance_stored(self) -> None:
        d = Deduplicator(tolerance=D("5.00"))
        assert d.tolerance == D("5.00")

    async def test_null_timeframe_passed_through(self) -> None:
        repo = self._repo(None)
        d = Deduplicator(tolerance=D("1"))
        setup = _setup(timeframe=None)
        await d.find_existing(setup, repo)
        _, kwargs = repo.find_duplicate.call_args
        assert kwargs["timeframe"] is None
