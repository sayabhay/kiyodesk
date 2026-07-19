"""Tests for OpportunityRepository (Task 2)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.database.base import Base
from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity
from app.repositories.opportunity_repository import OpportunityRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

D = Decimal


# ---------------------------------------------------------------------------
# Shared in-memory DB fixture
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


def _opp(**overrides: object) -> TradeOpportunity:
    defaults: dict[str, object] = dict(
        strategy="ICT Pure OTE",
        symbol="BTC",
        direction="long",
        entry=D("64000"),
        stop_loss=D("63500"),
        take_profit=D("65000"),
        risk_reward=D("2.0"),
        status=OpportunityStatus.ACTIVE,
        trade_setup_json='{"symbol":"BTC"}',
        entry_tolerance=D("1"),
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    defaults.update(overrides)
    return TradeOpportunity(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create / get
# ---------------------------------------------------------------------------


class TestCreateAndGet:
    async def test_create_returns_with_id(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        opp = _opp()
        saved = await repo.create(opp)
        assert saved.id is not None
        assert saved.id >= 1

    async def test_get_returns_saved_record(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        saved = await repo.create(_opp())
        fetched = await repo.get(saved.id)
        assert fetched is not None
        assert fetched.symbol == "BTC"
        assert fetched.entry == D("64000")

    async def test_get_unknown_id_returns_none(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        assert await repo.get(9999) is None


# ---------------------------------------------------------------------------
# list / list_active
# ---------------------------------------------------------------------------


class TestList:
    async def test_list_returns_all(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(symbol="BTC"))
        await repo.create(_opp(symbol="ETH"))
        result = await repo.list_all()
        assert len(result) == 2

    async def test_list_filters_by_symbol(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(symbol="BTC"))
        await repo.create(_opp(symbol="ETH"))
        result = await repo.list_all(symbol="BTC")
        assert len(result) == 1
        assert result[0].symbol == "BTC"

    async def test_list_filters_by_status(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(status=OpportunityStatus.ACTIVE))
        await repo.create(_opp(status=OpportunityStatus.TAKEN))
        active = await repo.list_all(status=OpportunityStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].status == "active"

    async def test_list_active_returns_only_active(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(status=OpportunityStatus.ACTIVE))
        await repo.create(_opp(status=OpportunityStatus.REJECTED))
        await repo.create(_opp(status=OpportunityStatus.EXPIRED))
        active = await repo.list_active()
        assert len(active) == 1

    async def test_list_symbol_case_insensitive(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(symbol="BTC"))
        result = await repo.list_all(symbol="btc")
        assert len(result) == 1

    async def test_list_ordered_newest_first(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        t1 = datetime(2026, 1, 1, 10, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 11, tzinfo=UTC)
        await repo.create(_opp(created_at=t1, updated_at=t1))
        await repo.create(_opp(created_at=t2, updated_at=t2))
        result = await repo.list_all()
        assert result[0].created_at >= result[1].created_at

    async def test_list_limit_respected(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        for _ in range(5):
            await repo.create(_opp())
        result = await repo.list_all(limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_update_persists_status_change(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        opp = await repo.create(_opp())
        opp.status = OpportunityStatus.TAKEN
        updated = await repo.update(opp)
        assert updated.status == "taken"

    async def test_update_sets_updated_at(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        before = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(seconds=2)
        opp = await repo.create(_opp())
        await repo.update(opp)
        # SQLite returns naive datetimes; strip tzinfo for comparison
        updated = opp.updated_at.replace(tzinfo=None) if opp.updated_at.tzinfo else opp.updated_at
        assert updated >= before


# ---------------------------------------------------------------------------
# find_duplicate
# ---------------------------------------------------------------------------


class TestFindDuplicate:
    async def test_exact_match_returns_record(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(entry=D("64000"), entry_tolerance=D("1")))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "long", D("64000"), D("1"))
        assert result is not None

    async def test_entry_within_tolerance_returns_record(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(entry=D("64000"), timeframe="15m"))
        # Entry differs by 0.5, tolerance is 1.0 → within range
        result = await repo.find_duplicate(
            "ICT Pure OTE", "BTC", "15m", "long", D("64000.5"), D("1")
        )
        assert result is not None

    async def test_entry_outside_tolerance_returns_none(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(entry=D("64000")))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "long", D("64010"), D("1"))
        assert result is None

    async def test_different_direction_returns_none(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(direction="long"))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "short", D("64000"), D("1"))
        assert result is None

    async def test_non_active_status_not_returned(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(status=OpportunityStatus.TAKEN))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "long", D("64000"), D("1"))
        assert result is None

    async def test_different_timeframe_returns_none(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(timeframe="15m"))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", "1h", "long", D("64000"), D("1"))
        assert result is None

    async def test_null_timeframe_matches_null(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(timeframe=None))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "long", D("64000"), D("1"))
        assert result is not None

    async def test_different_symbol_returns_none(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(symbol="ETH"))
        result = await repo.find_duplicate("ICT Pure OTE", "BTC", None, "long", D("64000"), D("1"))
        assert result is None
