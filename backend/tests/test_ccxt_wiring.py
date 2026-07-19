"""Tests for CCXTProvider wiring into ProviderManager and main.py (Task 5)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import Settings
from app.main import _build_provider_manager, create_app
from app.providers.ccxt.provider import CCXTProvider
from app.providers.errors import ProviderError, ProviderRateLimitError, ProviderResponseError
from fastapi.testclient import TestClient


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


class TestBuildProviderManager:
    def test_ccxt_binance_included_in_names(self) -> None:
        settings = _settings(market_providers="ccxt_binance,coingecko")
        mgr = _build_provider_manager(settings)
        assert "ccxt_binance" in mgr.names()

    def test_ccxt_binance_is_ccxt_provider_instance(self) -> None:
        settings = _settings(market_providers="ccxt_binance")
        mgr = _build_provider_manager(settings)
        provider = mgr.get("ccxt_binance")
        assert isinstance(provider, CCXTProvider)

    def test_ccxt_bybit_registered_when_configured(self) -> None:
        settings = _settings(ccxt_exchange="bybit", market_providers="ccxt_bybit,coingecko")
        mgr = _build_provider_manager(settings)
        assert "ccxt_bybit" in mgr.names()

    def test_provider_order_preserved(self) -> None:
        settings = _settings(market_providers="ccxt_binance,binance,coingecko")
        mgr = _build_provider_manager(settings)
        names = mgr.names()
        assert names.index("ccxt_binance") < names.index("binance")
        assert names.index("binance") < names.index("coingecko")

    def test_unknown_ccxt_provider_name_skipped(self) -> None:
        """A provider name not matching any key is silently skipped."""
        settings = _settings(market_providers="ccxt_kraken,coingecko")
        mgr = _build_provider_manager(settings)
        # ccxt_kraken not in available — only coingecko registered
        assert "coingecko" in mgr.names()
        assert "ccxt_kraken" not in mgr.names()

    def test_existing_providers_unaffected(self) -> None:
        settings = _settings(market_providers="binance,coingecko")
        mgr = _build_provider_manager(settings)
        assert "binance" in mgr.names()
        assert "coingecko" in mgr.names()
        assert "ccxt_binance" not in mgr.names()


class TestProviderManagerFailover:
    async def test_failover_from_ccxt_to_coingecko_on_response_error(self) -> None:
        """ProviderManager falls over from ccxt_binance to coingecko on ProviderResponseError."""
        from datetime import UTC, datetime
        from decimal import Decimal

        from app.providers.manager import ProviderManager
        from app.schemas.market import MarketSnapshot

        ccxt_provider = MagicMock()
        ccxt_provider.name = "ccxt_binance"
        ccxt_provider.get_market_snapshot = AsyncMock(
            side_effect=ProviderResponseError("CCXT failed")
        )

        coingecko_provider = MagicMock()
        coingecko_provider.name = "coingecko"
        fallback_snap = MarketSnapshot(
            symbol="BTC",
            provider="coingecko",
            captured_at=datetime.now(tz=UTC),
            price=Decimal("64000"),
        )
        coingecko_provider.get_market_snapshot = AsyncMock(return_value=fallback_snap)

        mgr = ProviderManager([ccxt_provider, coingecko_provider])
        result = await mgr.get_snapshot_with_failover("BTC")

        assert result.provider == "coingecko"
        assert result.price == Decimal("64000")

    async def test_failover_from_ccxt_to_coingecko_on_rate_limit(self) -> None:
        """ProviderManager falls over from ccxt_binance on ProviderRateLimitError."""
        from datetime import UTC, datetime
        from decimal import Decimal

        from app.providers.manager import ProviderManager
        from app.schemas.market import MarketSnapshot

        ccxt_provider = MagicMock()
        ccxt_provider.name = "ccxt_binance"
        ccxt_provider.get_market_snapshot = AsyncMock(
            side_effect=ProviderRateLimitError("rate limited")
        )

        coingecko_provider = MagicMock()
        coingecko_provider.name = "coingecko"
        fallback_snap = MarketSnapshot(
            symbol="BTC",
            provider="coingecko",
            captured_at=datetime.now(tz=UTC),
            price=Decimal("64000"),
        )
        coingecko_provider.get_market_snapshot = AsyncMock(return_value=fallback_snap)

        mgr = ProviderManager([ccxt_provider, coingecko_provider])
        result = await mgr.get_snapshot_with_failover("BTC")

        assert result.provider == "coingecko"

    async def test_all_providers_fail_raises_last_error(self) -> None:
        from app.providers.manager import ProviderManager

        p1 = MagicMock()
        p1.name = "ccxt_binance"
        p1.get_market_snapshot = AsyncMock(side_effect=ProviderResponseError("p1 failed"))

        p2 = MagicMock()
        p2.name = "coingecko"
        p2.get_market_snapshot = AsyncMock(side_effect=ProviderResponseError("p2 failed"))

        mgr = ProviderManager([p1, p2])
        with pytest.raises(ProviderError):
            await mgr.get_snapshot_with_failover("BTC")


class TestAppStartsWithCCXT:
    def test_app_creates_with_ccxt_in_provider_chain(self) -> None:
        """create_app() must succeed when ccxt_binance is in MARKET_PROVIDERS."""
        settings = _settings(market_providers="ccxt_binance,coingecko")
        app = create_app(settings)
        assert app is not None

    def test_health_endpoint_includes_ccxt_provider(self) -> None:
        settings = _settings(market_providers="ccxt_binance,coingecko")
        with TestClient(create_app(settings)) as client:
            r = client.get("/api/v1/health")
        assert r.status_code == 200
        providers = r.json()["providers"]
        assert "ccxt_binance" in providers
        assert "coingecko" in providers

    def test_providers_endpoint_lists_ccxt(self) -> None:
        settings = _settings(market_providers="ccxt_binance,binance")
        with TestClient(create_app(settings)) as client:
            r = client.get("/api/v1/providers")
        assert r.status_code == 200
        assert "ccxt_binance" in r.json()["providers"]
