"""Tests for CCXT exchange_factory (Task 2)."""

import ccxt.async_support as ccxt_async
import pytest
from app.core.config import Settings
from app.providers.ccxt.exchange_factory import (
    _SUPPORTED_EXCHANGES,
    close_exchange,
    create_exchange,
)
from app.providers.errors import ProviderConfigurationError


def _settings(**overrides: object) -> Settings:
    base = dict(
        database_url="sqlite+aiosqlite:///:memory:",
        scheduler_enabled=False,
        ccxt_exchange="binance",
        ccxt_market_type="future",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestCreateExchange:
    def test_binance_returns_binance_instance(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="binance"))
        assert isinstance(exchange, ccxt_async.binance)

    def test_bybit_returns_bybit_instance(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="bybit"))
        assert isinstance(exchange, ccxt_async.bybit)

    def test_bitget_returns_bitget_instance(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="bitget"))
        assert isinstance(exchange, ccxt_async.bitget)

    def test_unsupported_exchange_raises(self) -> None:
        with pytest.raises(ProviderConfigurationError, match="not supported"):
            create_exchange(_settings(ccxt_exchange="kraken"))

    def test_empty_exchange_raises(self) -> None:
        with pytest.raises(ProviderConfigurationError):
            create_exchange(_settings(ccxt_exchange=""))

    def test_okx_gets_swap_market_type_regardless_of_setting(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="okx", ccxt_market_type="future"))
        assert exchange.options.get("defaultType") == "swap"

    def test_binance_uses_configured_market_type(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="binance", ccxt_market_type="future"))
        assert exchange.options.get("defaultType") == "future"

    def test_binance_spot_market_type(self) -> None:
        exchange = create_exchange(_settings(ccxt_exchange="binance", ccxt_market_type="spot"))
        assert exchange.options.get("defaultType") == "spot"

    def test_rate_limiting_enabled(self) -> None:
        exchange = create_exchange(_settings())
        assert exchange.enableRateLimit is True

    def test_api_key_set_when_provided(self) -> None:
        exchange = create_exchange(
            _settings(ccxt_api_key="test-key", ccxt_api_secret="test-secret")
        )
        assert exchange.apiKey == "test-key"
        assert exchange.secret == "test-secret"

    def test_no_api_key_when_not_configured(self) -> None:
        exchange = create_exchange(_settings(ccxt_api_key=None, ccxt_api_secret=None))
        # apiKey should be empty/None when not set
        assert not exchange.apiKey

    def test_all_supported_exchanges_constructable(self) -> None:
        for exchange_id in _SUPPORTED_EXCHANGES:
            exchange = create_exchange(_settings(ccxt_exchange=exchange_id))
            assert exchange is not None


class TestCloseExchange:
    async def test_close_does_not_raise(self) -> None:
        exchange = create_exchange(_settings())
        # Should not raise even without having loaded markets
        await close_exchange(exchange)

    async def test_close_twice_does_not_raise(self) -> None:
        exchange = create_exchange(_settings())
        await close_exchange(exchange)
        await close_exchange(exchange)  # second close must be silent
