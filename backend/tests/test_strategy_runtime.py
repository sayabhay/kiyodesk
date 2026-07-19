"""Tests for StrategyRuntime and MarketListener (Task 6)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import Settings
from app.database.base import Base
from app.models.market_data import MarketData
from app.models.trade_opportunity import OpportunityStatus
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.market_listener import MarketListener
from app.runtime.strategy_runtime import StrategyRuntime, _market_data_to_bar
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

D = Decimal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as s:
        yield s
    await engine.dispose()


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        scheduler_enabled=False,
    )


def _market_row(
    symbol: str = "BTC",
    price: str = "64000",
    offset_minutes: int = 0,
) -> MarketData:
    return MarketData(
        symbol=symbol,
        provider="binance",
        price=D(price),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=offset_minutes),
    )


# ---------------------------------------------------------------------------
# _market_data_to_bar
# ---------------------------------------------------------------------------


class TestMarketDataToBar:
    def test_price_maps_to_all_ohlc_fields(self) -> None:
        row = _market_row(price="64000")
        bar = _market_data_to_bar(row)
        assert bar.open == D("64000")
        assert bar.high == D("64000")
        assert bar.low == D("64000")
        assert bar.close == D("64000")

    def test_volume_is_zero(self) -> None:
        bar = _market_data_to_bar(_market_row())
        assert bar.volume == D("0")

    def test_timestamp_preserved(self) -> None:
        row = _market_row()
        bar = _market_data_to_bar(row)
        assert bar.timestamp == row.captured_at

    def test_none_price_maps_to_zero(self) -> None:
        row = _market_row()
        row.price = None
        bar = _market_data_to_bar(row)
        assert bar.close == D("0")


# ---------------------------------------------------------------------------
# StrategyRuntime.on_market_update
# ---------------------------------------------------------------------------


class TestStrategyRuntime:
    async def test_returns_none_when_no_bars(self) -> None:
        """No market history → no evaluation → None."""
        settings = _settings()
        runtime = StrategyRuntime(settings)

        # Patch AsyncSessionLocal to use an empty in-memory DB
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        with patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory):
            result = await runtime.on_market_update("BTC")

        assert result is None
        await engine.dispose()

    async def test_returns_none_when_single_bar(self) -> None:
        """Fewer than 2 bars → None (engine needs at least 2)."""
        settings = _settings()
        runtime = StrategyRuntime(settings)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as s:
            repo = MarketDataRepository(s)
            from app.schemas.market import MarketSnapshot

            snap = MarketSnapshot(
                symbol="BTC",
                provider="binance",
                captured_at=datetime(2026, 1, 1, tzinfo=UTC),
                price=D("64000"),
            )
            await repo.store_if_new(snap)

        with patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory):
            result = await runtime.on_market_update("BTC")

        assert result is None
        await engine.dispose()

    async def test_returns_none_when_strategy_finds_no_setup(self) -> None:
        """Flat bar history produces no setup → returns None."""
        settings = _settings()
        runtime = StrategyRuntime(settings)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert 20 flat bars
        async with factory() as s:
            for i in range(20):
                s.add(
                    MarketData(
                        symbol="BTC",
                        provider="binance",
                        price=D("64000"),
                        captured_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
                    )
                )
            await s.commit()

        with patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory):
            result = await runtime.on_market_update("BTC")

        assert result is None
        await engine.dispose()

    async def test_creates_opportunity_when_setup_detected(self) -> None:
        """When StrategyService returns a TradeSetup, an opportunity is persisted."""
        from app.domain.strategy.models.config import StrategyConfig
        from app.domain.strategy.models.trade_setup import TradeSetup

        settings = _settings()
        runtime = StrategyRuntime(settings)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert 2 bars (enough to not short-circuit)
        async with factory() as s:
            for i in range(2):
                s.add(
                    MarketData(
                        symbol="BTC",
                        provider="binance",
                        price=D("64000"),
                        captured_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
                    )
                )
            await s.commit()

        # Mock StrategyService to return a TradeSetup
        fake_setup = TradeSetup(
            symbol="BTC",
            direction="long",
            entry=D("64000"),
            stop_loss=D("63500"),
            take_profit=D("65000"),
            risk_reward=D("2.0"),
            timeframe=None,
            reasons=["Bullish BOS confirmed"],
            warnings=[],
            ote_top=D("63820"),
            ote_bottom=D("63580"),
            leg_low=D("63000"),
            leg_high=D("65000"),
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            config_snapshot=StrategyConfig(),
        )

        with (
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                return_value=fake_setup,
            ),
        ):
            result = await runtime.on_market_update("BTC")

        assert result is not None
        assert result.symbol == "BTC"
        assert result.status == OpportunityStatus.ACTIVE

        # Verify persisted in DB
        async with factory() as s:
            opp_repo = OpportunityRepository(s)
            active = await opp_repo.list_active()
            assert len(active) == 1

        await engine.dispose()


# ---------------------------------------------------------------------------
# MarketListener
# ---------------------------------------------------------------------------


class TestMarketListener:
    async def test_calls_runtime_on_invoke(self) -> None:
        runtime = MagicMock()
        runtime.on_market_update = AsyncMock(return_value=None)
        listener = MarketListener(runtime)
        await listener("BTC")
        runtime.on_market_update.assert_called_once_with("BTC")

    async def test_swallows_runtime_errors(self) -> None:
        """A runtime error must not propagate — scheduler must continue."""
        runtime = MagicMock()
        runtime.on_market_update = AsyncMock(side_effect=RuntimeError("test error"))
        listener = MarketListener(runtime)
        # Should not raise
        await listener("ETH")

    async def test_passes_symbol_through(self) -> None:
        runtime = MagicMock()
        runtime.on_market_update = AsyncMock(return_value=None)
        listener = MarketListener(runtime)
        await listener("ETH")
        runtime.on_market_update.assert_called_once_with("ETH")
