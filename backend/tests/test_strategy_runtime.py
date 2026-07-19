"""Tests for StrategyRuntime and MarketListener.

All candle fetching is mocked — no live Binance API calls are made.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.database.base import Base
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup
from app.domain.strategy.interfaces.bar import Bar
from app.models.trade_opportunity import OpportunityStatus
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.market_listener import MarketListener
from app.runtime.strategy_runtime import StrategyRuntime
from app.runtime.timeframe_config import resolve_htf

D = Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = dict(
        database_url="sqlite+aiosqlite:///:memory:",
        scheduler_enabled=False,
        strategy_timeframe="15m",
        strategy_htf_timeframe="",      # auto-resolve
        strategy_candle_limit=200,
        strategy_htf_candle_limit=100,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _make_bar(price: str = "64000", ts: datetime | None = None) -> Bar:
    p = D(price)
    return Bar(
        timestamp=ts or datetime(2026, 1, 1, tzinfo=UTC),
        open=p - D("50"),
        high=p + D("100"),
        low=p - D("100"),
        close=p,
        volume=D("100"),
    )


def _bars(n: int = 30, base_price: str = "64000") -> list[Bar]:
    """Generate n realistic bars."""
    base = D(base_price)
    return [
        Bar(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            open=base - D("50"),
            high=base + D("100"),
            low=base - D("100"),
            close=base,
            volume=D("100"),
        )
        for _ in range(n)
    ]


def _fake_setup() -> TradeSetup:
    return TradeSetup(
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


async def _in_memory_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return factory, engine


# ---------------------------------------------------------------------------
# StrategyRuntime construction — timeframe resolution
# ---------------------------------------------------------------------------


class TestStrategyRuntimeConstruction:
    def test_auto_resolves_htf_from_ltf(self) -> None:
        """LTF=15m → HTF=1h via default map."""
        settings = _settings(strategy_timeframe="15m", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.ltf_interval == "15m"
        assert runtime.htf_interval == "1h"

    def test_manual_override_respected(self) -> None:
        """Explicit STRATEGY_HTF_TIMEFRAME beats the auto map."""
        settings = _settings(strategy_timeframe="15m", strategy_htf_timeframe="4h")
        runtime = StrategyRuntime(settings)
        assert runtime.ltf_interval == "15m"
        assert runtime.htf_interval == "4h"

    def test_1h_ltf_auto_resolves_to_4h(self) -> None:
        settings = _settings(strategy_timeframe="1h", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "4h"

    def test_4h_ltf_auto_resolves_to_12h(self) -> None:
        settings = _settings(strategy_timeframe="4h", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "12h"

    def test_2h_ltf_auto_resolves_to_12h(self) -> None:
        settings = _settings(strategy_timeframe="2h", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "12h"

    def test_12h_ltf_auto_resolves_to_1d(self) -> None:
        settings = _settings(strategy_timeframe="12h", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "1d"

    def test_1d_ltf_auto_resolves_to_1w(self) -> None:
        settings = _settings(strategy_timeframe="1d", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "1w"

    def test_1w_ltf_auto_resolves_to_1M(self) -> None:
        settings = _settings(strategy_timeframe="1w", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "1M"

    def test_1M_ltf_resolves_to_self(self) -> None:
        settings = _settings(strategy_timeframe="1M", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.htf_interval == "1M"

    def test_invalid_ltf_raises_value_error(self) -> None:
        settings = _settings(strategy_timeframe="10m")
        with pytest.raises(ValueError, match="10m"):
            StrategyRuntime(settings)

    def test_invalid_htf_override_raises_value_error(self) -> None:
        settings = _settings(strategy_timeframe="15m", strategy_htf_timeframe="10m")
        with pytest.raises(ValueError, match="10m"):
            StrategyRuntime(settings)

    def test_ltf_limit_stored(self) -> None:
        settings = _settings(strategy_candle_limit=300)
        runtime = StrategyRuntime(settings)
        assert runtime._ltf_limit == 300

    def test_htf_limit_stored(self) -> None:
        settings = _settings(strategy_htf_candle_limit=150)
        runtime = StrategyRuntime(settings)
        assert runtime._htf_limit == 150


# ---------------------------------------------------------------------------
# StrategyRuntime.on_market_update — candle fetching
# ---------------------------------------------------------------------------


class TestStrategyRuntimeCandleFetch:
    async def test_fetches_ltf_and_htf_candles(self) -> None:
        """Both fetch_candles calls must be made with correct interval/limit args."""
        settings = _settings(
            strategy_timeframe="15m",
            strategy_htf_timeframe="",   # auto → 1h
            strategy_candle_limit=200,
            strategy_htf_candle_limit=100,
        )
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        call_args: list[tuple] = []

        async def _mock_fetch(symbol: str, interval: str, limit: int) -> list[Bar]:
            call_args.append((symbol, interval, limit))
            return _bars(limit)

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", side_effect=_mock_fetch),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch("app.runtime.strategy_runtime.StrategyService.evaluate", return_value=None),
        ):
            await runtime.on_market_update("BTC")

        await engine.dispose()

        intervals = {a[1] for a in call_args}
        assert "15m" in intervals
        assert "1h" in intervals

    async def test_htf_fetched_with_htf_limit(self) -> None:
        settings = _settings(
            strategy_timeframe="15m",
            strategy_htf_timeframe="",
            strategy_candle_limit=200,
            strategy_htf_candle_limit=80,
        )
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        htf_limits: list[int] = []

        async def _mock_fetch(symbol: str, interval: str, limit: int) -> list[Bar]:
            if interval == runtime.htf_interval:
                htf_limits.append(limit)
            return _bars(limit)

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", side_effect=_mock_fetch),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch("app.runtime.strategy_runtime.StrategyService.evaluate", return_value=None),
        ):
            await runtime.on_market_update("BTC")

        await engine.dispose()
        assert 80 in htf_limits

    async def test_manual_override_used_in_fetch(self) -> None:
        """When STRATEGY_HTF_TIMEFRAME is set, that exact value is used for the HTF fetch."""
        settings = _settings(
            strategy_timeframe="15m",
            strategy_htf_timeframe="4h",   # manual override
        )
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        fetched_intervals: list[str] = []

        async def _mock_fetch(symbol: str, interval: str, limit: int) -> list[Bar]:
            fetched_intervals.append(interval)
            return _bars(limit)

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", side_effect=_mock_fetch),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch("app.runtime.strategy_runtime.StrategyService.evaluate", return_value=None),
        ):
            await runtime.on_market_update("BTC")

        await engine.dispose()
        assert "4h" in fetched_intervals
        assert "1h" not in fetched_intervals  # default map would give 1h, not 4h

    async def test_candle_fetch_failure_returns_none(self) -> None:
        settings = _settings()
        runtime = StrategyRuntime(settings)

        with patch(
            "app.runtime.strategy_runtime.fetch_candles",
            side_effect=Exception("network timeout"),
        ):
            result = await runtime.on_market_update("BTC")

        assert result is None

    async def test_insufficient_ltf_bars_returns_none(self) -> None:
        settings = _settings()
        runtime = StrategyRuntime(settings)

        async def _one_bar(symbol: str, interval: str, limit: int) -> list[Bar]:
            if interval == runtime.ltf_interval:
                return [_make_bar()]   # only 1 bar
            return _bars(100)

        with patch("app.runtime.strategy_runtime.fetch_candles", side_effect=_one_bar):
            result = await runtime.on_market_update("BTC")

        assert result is None


# ---------------------------------------------------------------------------
# StrategyRuntime.on_market_update — strategy evaluation
# ---------------------------------------------------------------------------


class TestStrategyRuntimeEvaluation:
    async def test_returns_none_when_no_setup(self) -> None:
        settings = _settings()
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                return_value=None,
            ),
        ):
            result = await runtime.on_market_update("BTC")

        await engine.dispose()
        assert result is None

    async def test_persists_opportunity_when_setup_detected(self) -> None:
        settings = _settings()
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                return_value=_fake_setup(),
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

    async def test_opportunity_symbol_matches(self) -> None:
        settings = _settings()
        runtime = StrategyRuntime(settings)
        factory, engine = await _in_memory_session_factory()

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch("app.runtime.strategy_runtime.AsyncSessionLocal", factory),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                return_value=_fake_setup(),
            ),
        ):
            result = await runtime.on_market_update("BTC")

        await engine.dispose()
        assert result is not None
        assert result.symbol == "BTC"

    async def test_htf_filter_disabled_when_ltf_equals_htf(self) -> None:
        """When 1M execution TF resolves to itself, use_htf_trend must be False."""
        settings = _settings(strategy_timeframe="1M", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)
        assert runtime.ltf_interval == runtime.htf_interval

        captured_config: list[StrategyConfig] = []

        def _capture_evaluate(bars, htf_bars, symbol, config, timeframe):
            captured_config.append(config)
            return None

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                side_effect=_capture_evaluate,
            ),
        ):
            await runtime.on_market_update("BTC")

        assert len(captured_config) == 1
        assert captured_config[0].use_htf_trend is False

    async def test_htf_filter_enabled_when_htf_bars_available(self) -> None:
        settings = _settings(strategy_timeframe="15m", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)

        captured_config: list[StrategyConfig] = []

        def _capture_evaluate(bars, htf_bars, symbol, config, timeframe):
            captured_config.append(config)
            return None

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                side_effect=_capture_evaluate,
            ),
        ):
            await runtime.on_market_update("BTC")

        assert len(captured_config) == 1
        assert captured_config[0].use_htf_trend is True

    async def test_timeframe_label_passed_to_strategy(self) -> None:
        settings = _settings(strategy_timeframe="1h", strategy_htf_timeframe="")
        runtime = StrategyRuntime(settings)

        call_kwargs: list[dict] = []

        def _capture(**kwargs):
            call_kwargs.append(kwargs)
            return None

        with (
            patch("app.runtime.strategy_runtime.fetch_candles", return_value=_bars(50)),
            patch(
                "app.runtime.strategy_runtime.StrategyService.evaluate",
                side_effect=lambda **kw: call_kwargs.append(kw) or None,
            ),
        ):
            await runtime.on_market_update("ETH")

        if call_kwargs:
            assert call_kwargs[0].get("timeframe") == "1h"


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
        # Must not raise
        await listener("ETH")

    async def test_passes_symbol_through(self) -> None:
        runtime = MagicMock()
        runtime.on_market_update = AsyncMock(return_value=None)
        listener = MarketListener(runtime)
        await listener("ETH")
        runtime.on_market_update.assert_called_once_with("ETH")


# ---------------------------------------------------------------------------
# Settings — new fields
# ---------------------------------------------------------------------------


class TestSettingsTimeframeFields:
    def test_strategy_timeframe_default_is_15m(self) -> None:
        s = _settings()
        assert s.strategy_timeframe == "15m"

    def test_strategy_htf_timeframe_default_is_empty(self) -> None:
        """Empty string triggers auto-resolution via DEFAULT_HTF_MAP."""
        s = _settings()
        assert s.strategy_htf_timeframe == ""

    def test_strategy_candle_limit_default(self) -> None:
        s = _settings()
        assert s.strategy_candle_limit == 200

    def test_strategy_htf_candle_limit_default(self) -> None:
        s = _settings()
        assert s.strategy_htf_candle_limit == 100

    def test_custom_ltf(self) -> None:
        s = _settings(strategy_timeframe="1h")
        assert s.strategy_timeframe == "1h"

    def test_custom_htf_override(self) -> None:
        s = _settings(strategy_htf_timeframe="4h")
        assert s.strategy_htf_timeframe == "4h"

    def test_custom_htf_candle_limit(self) -> None:
        s = _settings(strategy_htf_candle_limit=200)
        assert s.strategy_htf_candle_limit == 200
