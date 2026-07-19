"""Unit coverage for the analytics calculator."""

from decimal import Decimal

import pytest
from app.analytics.calculator import compute_analytics
from app.models.trade import Trade


def _trade(
    *,
    status: str = "closed",
    profit_loss: str | None,
    symbol: str = "BTC",
) -> Trade:
    """Build a minimal Trade stub for calculator tests."""

    t = Trade(symbol=symbol, direction="long", entry_price=Decimal("60000"), status=status)
    t.id = 0
    t.profit_loss = Decimal(profit_loss) if profit_loss is not None else None
    return t


def test_no_trades_returns_zero_counts_and_none_metrics() -> None:
    """An empty journal returns zero counts and None for every computed metric."""

    result = compute_analytics([])

    assert result.total_trades == 0
    assert result.closed_trades == 0
    assert result.win_rate is None
    assert result.profit_factor is None
    assert result.expectancy is None


def test_only_open_trades_returns_none_metrics() -> None:
    """Open trades without P&L do not contribute to computed metrics."""

    result = compute_analytics([_trade(status="open", profit_loss=None)])

    assert result.total_trades == 1
    assert result.open_trades == 1
    assert result.closed_trades == 0
    assert result.win_rate is None


def test_all_winners_sets_profit_factor_to_none() -> None:
    """When gross loss is zero, profit_factor is undefined (no denominator)."""

    trades = [_trade(profit_loss="1000"), _trade(profit_loss="500")]
    result = compute_analytics(trades)

    assert result.winning_trades == 2
    assert result.losing_trades == 0
    assert result.profit_factor is None


def test_win_rate_calculation() -> None:
    """Win rate is the percentage of closed trades with positive P&L."""

    trades = [
        _trade(profit_loss="1000"),
        _trade(profit_loss="500"),
        _trade(profit_loss="-400"),
        _trade(profit_loss="-200"),
    ]
    result = compute_analytics(trades)

    assert result.win_rate == Decimal("50.000000")
    assert result.winning_trades == 2
    assert result.losing_trades == 2


def test_profit_factor_calculation() -> None:
    """Profit factor equals gross profit divided by gross loss."""

    trades = [
        _trade(profit_loss="1500"),  # gross profit = 1500
        _trade(profit_loss="-500"),  # gross loss   = 500
    ]
    result = compute_analytics(trades)

    assert result.profit_factor == Decimal("3.000000")


def test_expectancy_is_average_pnl_per_trade() -> None:
    """Expectancy is the mean P&L across all closed trades."""

    trades = [
        _trade(profit_loss="600"),
        _trade(profit_loss="-200"),
    ]
    result = compute_analytics(trades)

    assert result.expectancy == Decimal("200.000000")
    assert result.total_profit_loss == Decimal("400")


def test_largest_win_and_loss() -> None:
    """Largest win is max P&L; largest loss is min P&L."""

    trades = [
        _trade(profit_loss="2000"),
        _trade(profit_loss="500"),
        _trade(profit_loss="-100"),
        _trade(profit_loss="-800"),
    ]
    result = compute_analytics(trades)

    assert result.largest_win == Decimal("2000")
    assert result.largest_loss == Decimal("-800")


def test_breakeven_trades_are_counted_separately() -> None:
    """Trades with P&L of zero are counted as breakeven, not wins or losses."""

    trades = [
        _trade(profit_loss="1000"),
        _trade(profit_loss="0"),
        _trade(profit_loss="-500"),
    ]
    result = compute_analytics(trades)

    assert result.breakeven_trades == 1
    assert result.winning_trades == 1
    assert result.losing_trades == 1


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_200() -> None:
    """The analytics route returns a valid response with an empty in-memory journal."""

    from collections.abc import AsyncIterator

    from app.database.base import Base
    from app.database.session import get_session
    from app.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Isolated in-memory engine so this test never touches kiyodesk.db
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with TestSession() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        response = client.get("/api/v1/analytics")

    assert response.status_code == 200
    data = response.json()
    assert data["total_trades"] == 0
    assert data["win_rate"] is None

    await test_engine.dispose()
