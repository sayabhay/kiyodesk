"""Tests for CandleLoader (Task 1). No live exchange calls — all mocked."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.providers.errors import ProviderResponseError
from app.runtime.candle_loader import CandleLoader, _row_to_bar

D = Decimal


def _settings(**overrides: object) -> Settings:
    base = dict(
        database_url="sqlite+aiosqlite:///:memory:",
        scheduler_enabled=False,
        ccxt_exchange="binance",
        ccxt_market_type="future",
        ccxt_symbol_map="BTC:BTC/USDT:USDT,ETH:ETH/USDT:USDT",
        strategy_timeframe="15m",
        strategy_htf_timeframe="4h",
        strategy_candle_limit=200,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# Sample CCXT OHLCV rows: [timestamp_ms, open, high, low, close, volume]
_SAMPLE_ROWS: list[list[object]] = [
    [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5],
    [1784400900000, 64200.0, 64600.0, 64100.0, 64400.0, 120.3],
    [1784401800000, 64400.0, 65000.0, 64300.0, 64900.0, 200.1],
]


# ---------------------------------------------------------------------------
# _row_to_bar unit tests
# ---------------------------------------------------------------------------


class TestRowToBar:
    def test_timestamp_converted_from_milliseconds(self) -> None:
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5]
        bar = _row_to_bar(row)
        expected = datetime.fromtimestamp(1784400000.0, tz=UTC)
        assert bar.timestamp == expected

    def test_timestamp_is_utc_aware(self) -> None:
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5]
        bar = _row_to_bar(row)
        assert bar.timestamp.tzinfo is not None

    def test_ohlcv_fields_converted_to_decimal(self) -> None:
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5]
        bar = _row_to_bar(row)
        assert bar.open == D("64000.0")
        assert bar.high == D("64500.0")
        assert bar.low == D("63800.0")
        assert bar.close == D("64200.0")
        assert bar.volume == D("150.5")

    def test_high_greater_than_low(self) -> None:
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5]
        bar = _row_to_bar(row)
        assert bar.high > bar.low

    def test_open_close_distinct_from_high_low(self) -> None:
        """Real candles must have distinct OHLC — not flat like price snapshots."""
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, 150.5]
        bar = _row_to_bar(row)
        assert bar.open != bar.high
        assert bar.low != bar.close

    def test_string_values_parsed(self) -> None:
        row: list[object] = [1784400000000, "64000.5", "64500.1", "63800.9", "64200.3", "150"]
        bar = _row_to_bar(row)
        assert bar.open == D("64000.5")

    def test_none_volume_becomes_zero(self) -> None:
        row: list[object] = [1784400000000, 64000.0, 64500.0, 63800.0, 64200.0, None]
        bar = _row_to_bar(row)
        assert bar.volume == D("0")


# ---------------------------------------------------------------------------
# CandleLoader.fetch_bars tests
# ---------------------------------------------------------------------------


def _mock_exchange(rows: list[list[object]]) -> object:
    exchange = AsyncMock()
    exchange.fetch_ohlcv = AsyncMock(return_value=rows)
    exchange.close = AsyncMock()
    return exchange


class TestCandleLoader:
    def _patched(self, exchange: object) -> tuple:
        create_p = patch("app.runtime.candle_loader.create_exchange", return_value=exchange)
        close_p = patch("app.runtime.candle_loader.close_exchange", new_callable=AsyncMock)
        return create_p, close_p

    async def test_returns_bars_in_chronological_order(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("BTC", "15m", limit=3)

        assert len(bars) == 3
        # Chronological: each timestamp >= previous
        for i in range(1, len(bars)):
            assert bars[i].timestamp >= bars[i - 1].timestamp

    async def test_bars_have_distinct_high_low(self) -> None:
        """The whole point — real candles have distinct highs and lows."""
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("BTC", "15m")

        for bar in bars:
            assert bar.high >= bar.low
            # At least one bar should have high > low
        assert any(b.high > b.low for b in bars)

    async def test_correct_decimal_values(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("BTC")

        assert bars[0].open == D("64000.0")
        assert bars[0].high == D("64500.0")
        assert bars[0].low == D("63800.0")
        assert bars[0].close == D("64200.0")

    async def test_fetch_ohlcv_called_with_correct_args(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            await loader.fetch_bars("BTC", timeframe="4h", limit=100)

        exchange.fetch_ohlcv.assert_called_once_with("BTC/USDT:USDT", "4h", limit=100)  # type: ignore[attr-defined]

    async def test_ccxt_exception_raises_provider_response_error(self) -> None:
        exchange = AsyncMock()
        exchange.fetch_ohlcv = AsyncMock(side_effect=Exception("network error"))
        exchange.close = AsyncMock()
        create_p, close_p = self._patched(exchange)
        with create_p, close_p, pytest.raises(ProviderResponseError, match="fetch_ohlcv failed"):
            loader = CandleLoader(_settings())
            await loader.fetch_bars("BTC")

    async def test_unknown_symbol_returns_empty_list(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("SOL")  # not in symbol map
        assert bars == []

    async def test_empty_ohlcv_response_returns_empty_list(self) -> None:
        exchange = _mock_exchange([])
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("BTC")
        assert bars == []

    async def test_eth_symbol_resolved_correctly(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            await loader.fetch_bars("ETH", timeframe="15m", limit=50)

        exchange.fetch_ohlcv.assert_called_once_with("ETH/USDT:USDT", "15m", limit=50)  # type: ignore[attr-defined]

    async def test_symbol_uppercased_before_lookup(self) -> None:
        exchange = _mock_exchange(_SAMPLE_ROWS)
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            loader = CandleLoader(_settings())
            bars = await loader.fetch_bars("btc")  # lowercase
        assert len(bars) == 3  # resolved correctly


# ---------------------------------------------------------------------------
# Settings new fields
# ---------------------------------------------------------------------------


class TestSettingsNewFields:
    def test_strategy_timeframe_default(self) -> None:
        s = _settings()
        assert s.strategy_timeframe == "15m"

    def test_strategy_htf_timeframe_default(self) -> None:
        s = _settings()
        assert s.strategy_htf_timeframe == "4h"

    def test_strategy_candle_limit_default(self) -> None:
        s = _settings()
        assert s.strategy_candle_limit == 200

    def test_custom_timeframe(self) -> None:
        s = _settings(strategy_timeframe="1h")
        assert s.strategy_timeframe == "1h"

    def test_custom_candle_limit(self) -> None:
        s = _settings(strategy_candle_limit=500)
        assert s.strategy_candle_limit == 500
