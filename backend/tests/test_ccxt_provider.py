"""Tests for CCXTProvider (Task 4). No live exchange calls — all mocked."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import ccxt.async_support as ccxt_async
import pytest
from app.core.config import Settings
from app.providers.ccxt.provider import CCXTProvider
from app.providers.errors import ProviderRateLimitError, ProviderResponseError


def _settings(**overrides: object) -> Settings:
    base = dict(
        database_url="sqlite+aiosqlite:///:memory:",
        scheduler_enabled=False,
        ccxt_exchange="binance",
        ccxt_market_type="future",
        ccxt_symbol_map="BTC:BTC/USDT:USDT,ETH:ETH/USDT:USDT",
        cache_seconds=60,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _mock_exchange(
    ticker: dict | None = None,
    funding: dict | None = None,
    oi: dict | None = None,
    ticker_error: Exception | None = None,
    funding_error: Exception | None = None,
    oi_error: Exception | None = None,
) -> MagicMock:
    exchange = MagicMock()

    if ticker_error:
        exchange.fetch_ticker = AsyncMock(side_effect=ticker_error)
    else:
        exchange.fetch_ticker = AsyncMock(
            return_value=ticker or {"last": 64000.0, "timestamp": 1784400000000}
        )

    if funding_error:
        exchange.fetch_funding_rate = AsyncMock(side_effect=funding_error)
    else:
        exchange.fetch_funding_rate = AsyncMock(return_value=funding or {"fundingRate": 0.0001})

    if oi_error:
        exchange.fetch_open_interest = AsyncMock(side_effect=oi_error)
    else:
        exchange.fetch_open_interest = AsyncMock(
            return_value=oi or {"openInterestAmount": 100000.0}
        )

    exchange.load_markets = AsyncMock(return_value={})
    exchange.close = AsyncMock()
    return exchange


class TestCCXTProviderName:
    def test_name_is_ccxt_binance(self) -> None:
        p = CCXTProvider(_settings(ccxt_exchange="binance"))
        assert p.name == "ccxt_binance"

    def test_name_is_ccxt_bybit(self) -> None:
        p = CCXTProvider(_settings(ccxt_exchange="bybit"))
        assert p.name == "ccxt_bybit"

    def test_name_is_ccxt_bitget(self) -> None:
        p = CCXTProvider(_settings(ccxt_exchange="bitget"))
        assert p.name == "ccxt_bitget"


class TestCCXTProviderHealth:
    async def test_health_true_when_load_markets_succeeds(self) -> None:
        mock_exchange = _mock_exchange()
        with (
            patch("app.providers.ccxt.provider.create_exchange", return_value=mock_exchange),
            patch("app.providers.ccxt.provider.close_exchange", new_callable=AsyncMock),
        ):
            p = CCXTProvider(_settings())
            assert await p.health() is True

    async def test_health_false_when_load_markets_fails(self) -> None:
        mock_exchange = _mock_exchange()
        mock_exchange.load_markets = AsyncMock(side_effect=Exception("network error"))
        with (
            patch("app.providers.ccxt.provider.create_exchange", return_value=mock_exchange),
            patch("app.providers.ccxt.provider.close_exchange", new_callable=AsyncMock),
        ):
            p = CCXTProvider(_settings())
            assert await p.health() is False


class TestGetMarketSnapshot:
    def _patched(self, exchange: MagicMock) -> tuple:
        create_patch = patch("app.providers.ccxt.provider.create_exchange", return_value=exchange)
        close_patch = patch("app.providers.ccxt.provider.close_exchange", new_callable=AsyncMock)
        return create_patch, close_patch

    async def test_successful_snapshot(self) -> None:
        exchange = _mock_exchange(
            ticker={"last": 64000.0, "timestamp": 1784400000000},
            funding={"fundingRate": 0.0001},
            oi={"openInterestAmount": 100000.0},
        )
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("BTC")

        assert snap.symbol == "BTC"
        assert snap.provider == "ccxt_binance"
        assert snap.price == Decimal("64000.0")
        assert snap.funding_rate == Decimal("0.0001")
        assert snap.open_interest == Decimal(str(100000.0)) * Decimal("64000.0")
        assert snap.liquidation_volume is None

    async def test_symbol_normalised_to_uppercase(self) -> None:
        exchange = _mock_exchange()
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("btc")
        assert snap.symbol == "BTC"

    async def test_unsupported_symbol_raises_response_error(self) -> None:
        exchange = _mock_exchange()
        create_p, close_p = self._patched(exchange)
        with create_p, close_p, pytest.raises(ProviderResponseError, match="symbol map"):
            p = CCXTProvider(_settings())
            await p.get_market_snapshot("SOL")

    async def test_rate_limit_from_ticker_raises_rate_limit_error(self) -> None:
        exchange = _mock_exchange(ticker_error=ccxt_async.RateLimitExceeded("429"))
        create_p, close_p = self._patched(exchange)
        with create_p, close_p, pytest.raises(ProviderRateLimitError):
            p = CCXTProvider(_settings())
            await p.get_market_snapshot("BTC")

    async def test_network_error_from_ticker_raises_response_error(self) -> None:
        exchange = _mock_exchange(ticker_error=Exception("connection refused"))
        create_p, close_p = self._patched(exchange)
        with create_p, close_p, pytest.raises(ProviderResponseError, match="fetch_ticker"):
            p = CCXTProvider(_settings())
            await p.get_market_snapshot("BTC")

    async def test_funding_error_produces_none_rate(self) -> None:
        exchange = _mock_exchange(funding_error=Exception("not supported"))
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("BTC")
        assert snap.funding_rate is None
        assert snap.price is not None  # ticker still succeeded

    async def test_oi_error_produces_none_oi(self) -> None:
        exchange = _mock_exchange(oi_error=Exception("not supported"))
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("BTC")
        assert snap.open_interest is None
        assert snap.price is not None

    async def test_both_funding_and_oi_errors_no_crash(self) -> None:
        exchange = _mock_exchange(
            funding_error=Exception("no funding"),
            oi_error=Exception("no oi"),
        )
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("BTC")
        assert snap.price == Decimal("64000.0")
        assert snap.funding_rate is None
        assert snap.open_interest is None

    async def test_eth_snapshot(self) -> None:
        exchange = _mock_exchange(ticker={"last": 3200.0, "timestamp": 1784400000000})
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            snap = await p.get_market_snapshot("ETH")
        assert snap.symbol == "ETH"
        assert snap.price == Decimal("3200.0")

    async def test_fetch_ticker_called_with_ccxt_symbol(self) -> None:
        exchange = _mock_exchange()
        create_p, close_p = self._patched(exchange)
        with create_p, close_p:
            p = CCXTProvider(_settings())
            await p.get_market_snapshot("BTC")
        exchange.fetch_ticker.assert_called_once_with("BTC/USDT:USDT")
