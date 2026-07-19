"""Tests for OpportunityManager create-or-update logic (Task 5)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.database.base import Base
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup
from app.models.trade_opportunity import OpportunityStatus
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.deduplicator import Deduplicator
from app.runtime.opportunity_manager import OpportunityManager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

D = Decimal


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _manager(session: AsyncSession, tolerance: D = D("1"), ttl: int = 4) -> OpportunityManager:
    repo = OpportunityRepository(session)
    dedup = Deduplicator(tolerance=tolerance)
    return OpportunityManager(repo, dedup, ttl_hours=ttl)


# ---------------------------------------------------------------------------
# create_or_update
# ---------------------------------------------------------------------------


class TestCreateOrUpdate:
    async def test_first_call_creates_new_record(self, session: AsyncSession) -> None:
        mgr = _manager(session)
        opp = await mgr.create_or_update(_setup())
        assert opp.id is not None
        assert opp.status == OpportunityStatus.ACTIVE
        assert opp.symbol == "BTC"
        assert opp.direction == "long"
        assert opp.entry == D("64000")

    async def test_second_identical_call_updates_not_creates(self, session: AsyncSession) -> None:
        mgr = _manager(session)
        first = await mgr.create_or_update(_setup())
        second = await mgr.create_or_update(_setup())
        assert first.id == second.id  # same record

        # Verify only one row exists
        repo = OpportunityRepository(session)
        all_opps = await repo.list_all()
        assert len(all_opps) == 1

    async def test_different_entry_outside_tolerance_creates_new(
        self, session: AsyncSession
    ) -> None:
        mgr = _manager(session, tolerance=D("1"))
        await mgr.create_or_update(_setup(entry=D("64000")))
        await mgr.create_or_update(_setup(entry=D("64100")))  # >1 away
        repo = OpportunityRepository(session)
        assert len(await repo.list_all()) == 2

    async def test_different_direction_creates_new(self, session: AsyncSession) -> None:
        mgr = _manager(session)
        await mgr.create_or_update(_setup(direction="long"))
        await mgr.create_or_update(_setup(direction="short"))
        repo = OpportunityRepository(session)
        assert len(await repo.list_all()) == 2

    async def test_trade_setup_json_is_parseable(self, session: AsyncSession) -> None:
        mgr = _manager(session)
        setup = _setup()
        opp = await mgr.create_or_update(setup)
        # Must parse back to an equivalent TradeSetup
        parsed = TradeSetup.model_validate_json(opp.trade_setup_json)
        assert parsed.symbol == setup.symbol
        assert parsed.entry == setup.entry
        assert parsed.direction == setup.direction

    async def test_expires_at_is_set(self, session: AsyncSession) -> None:
        mgr = _manager(session, ttl=4)
        opp = await mgr.create_or_update(_setup())
        assert opp.expires_at is not None
        # Should be ~4 hours after created_at (allow 5s tolerance for test execution)
        delta = opp.expires_at - opp.created_at
        assert abs(delta.total_seconds() - 4 * 3600) < 5

    async def test_confidence_is_none(self, session: AsyncSession) -> None:
        opp = await _manager(session).create_or_update(_setup())
        assert opp.confidence is None

    async def test_market_regime_is_none(self, session: AsyncSession) -> None:
        opp = await _manager(session).create_or_update(_setup())
        assert opp.market_regime is None

    async def test_status_is_active(self, session: AsyncSession) -> None:
        opp = await _manager(session).create_or_update(_setup())
        assert opp.status == "active"

    async def test_update_refreshes_setup_json(self, session: AsyncSession) -> None:
        mgr = _manager(session)
        setup_v1 = _setup(entry=D("64000"), stop_loss=D("63500"))
        setup_v2 = _setup(entry=D("64000"), stop_loss=D("63400"))  # same entry, different SL
        await mgr.create_or_update(setup_v1)
        opp2 = await mgr.create_or_update(setup_v2)
        parsed = TradeSetup.model_validate_json(opp2.trade_setup_json)
        assert parsed.stop_loss == D("63400")

    async def test_entry_tolerance_stored_on_opportunity(self, session: AsyncSession) -> None:
        mgr = _manager(session, tolerance=D("5"))
        opp = await mgr.create_or_update(_setup())
        assert opp.entry_tolerance == D("5")
