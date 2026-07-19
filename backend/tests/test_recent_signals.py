"""Tests for GET /api/v1/opportunities/recent and list_since repository method (Task 1)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.database.base import Base
from app.database.session import get_session
from app.main import create_app
from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity
from app.repositories.opportunity_repository import OpportunityRepository
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

D = Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opp(
    symbol: str = "BTC",
    status: str = OpportunityStatus.ACTIVE,
    created_offset_minutes: int = 0,
) -> TradeOpportunity:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=created_offset_minutes)
    return TradeOpportunity(
        strategy="ICT Pure OTE",
        symbol=symbol,
        direction="long",
        entry=D("64000"),
        stop_loss=D("63500"),
        take_profit=D("65000"),
        risk_reward=D("2.0"),
        status=status,
        trade_setup_json="{}",
        entry_tolerance=D("1"),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def client() -> TestClient:  # type: ignore[misc]
    from collections.abc import AsyncIterator

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override() -> AsyncIterator[AsyncSession]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override
    return TestClient(app)


# ---------------------------------------------------------------------------
# list_since repository tests
# ---------------------------------------------------------------------------


class TestListSince:
    async def test_returns_records_after_since(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(created_offset_minutes=-30))  # 30 min before baseline
        await repo.create(_opp(created_offset_minutes=30))  # 30 min after baseline
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline)
        assert len(result) == 1

    async def test_returns_empty_when_none_after_since(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(created_offset_minutes=-60))
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline)
        assert len(result) == 0

    async def test_only_active_returned(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(created_offset_minutes=10, status=OpportunityStatus.ACTIVE))
        await repo.create(_opp(created_offset_minutes=10, status=OpportunityStatus.TAKEN))
        await repo.create(_opp(created_offset_minutes=10, status=OpportunityStatus.REJECTED))
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline)
        assert len(result) == 1
        assert result[0].status == "active"

    async def test_filters_by_symbol(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(symbol="BTC", created_offset_minutes=10))
        await repo.create(_opp(symbol="ETH", created_offset_minutes=10))
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline, symbol="BTC")
        assert len(result) == 1
        assert result[0].symbol == "BTC"

    async def test_ordered_newest_first(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        await repo.create(_opp(created_offset_minutes=5))
        await repo.create(_opp(created_offset_minutes=10))
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline)
        assert result[0].created_at >= result[1].created_at

    async def test_returns_multiple_matching_records(self, session: AsyncSession) -> None:
        repo = OpportunityRepository(session)
        for i in range(5):
            await repo.create(_opp(created_offset_minutes=i + 1))
        baseline = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        result = await repo.list_since(since=baseline)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# GET /opportunities/recent endpoint tests
# ---------------------------------------------------------------------------


class TestRecentEndpoint:
    def test_returns_200_with_valid_since(self, client: TestClient) -> None:
        r = client.get("/api/v1/opportunities/recent?since=2026-01-01T00:00:00Z")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_returns_200_without_since(self, client: TestClient) -> None:
        r = client.get("/api/v1/opportunities/recent")
        assert r.status_code == 200

    def test_invalid_since_returns_422(self, client: TestClient) -> None:
        r = client.get("/api/v1/opportunities/recent?since=not-a-date")
        assert r.status_code == 422

    def test_future_since_returns_empty(self, client: TestClient) -> None:
        r = client.get("/api/v1/opportunities/recent?since=2099-01-01T00:00:00Z")
        assert r.status_code == 200
        assert r.json() == []

    def test_symbol_filter_accepted(self, client: TestClient) -> None:
        r = client.get("/api/v1/opportunities/recent?symbol=BTC")
        assert r.status_code == 200

    def test_route_in_openapi(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        assert "/api/v1/opportunities/recent" in r.json()["paths"]
