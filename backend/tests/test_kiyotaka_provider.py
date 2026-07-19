"""Kiyotaka provider and live market endpoint coverage without real API calls."""

import httpx
import pytest
from app.core.config import Settings
from app.main import create_app
from app.providers.errors import ProviderRateLimitError
from app.providers.kiyotaka import KiyotakaProvider
from app.providers.manager import ProviderManager
from app.providers.quota import SlidingWindowQuota
from fastapi.testclient import TestClient


def candle_transport(call_counter: list[int]) -> httpx.MockTransport:
    """Return a deterministic Kiyotaka-compatible candle response."""

    def handler(request: httpx.Request) -> httpx.Response:
        call_counter[0] += 1
        assert request.headers["X-Kiyotaka-Key"] == "test-key"
        assert request.url.path == "/v1/points"
        point_type = request.url.params["type"]
        assert point_type in {
            "TRADE_SIDE_AGNOSTIC_AGG",
            "OPEN_INTEREST_AGG",
            "FUNDING_RATE_AGG",
            "LIQUIDATION_AGG",
        }
        point = {"timestamp": {"s": 1_774_800_000}}
        if point_type == "TRADE_SIDE_AGNOSTIC_AGG":
            point["close"] = 123456.78
        elif point_type == "OPEN_INTEREST_AGG":
            point["close"] = 2_000_000_000
        elif point_type == "FUNDING_RATE_AGG":
            point["rateClose"] = 0.0001
        else:
            return httpx.Response(
                200,
                json={
                    "series": [
                        {
                            "id": {"side": "BUY"},
                            "points": [{"Point": {**point, "liquidations": 10}}],
                        },
                        {
                            "id": {"side": "SELL"},
                            "points": [{"Point": {**point, "liquidations": 20}}],
                        },
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"series": [{"points": [{"Point": point}]}]},
        )

    return httpx.MockTransport(handler)


def test_market_endpoint_returns_cached_normalized_candle_close() -> None:
    """A repeated endpoint request consumes only one Kiyotaka request within the cache TTL."""

    calls = [0]
    provider = KiyotakaProvider(
        Settings(kiyotaka_api_key="test-key"),
        transport=candle_transport(calls),
    )
    application = create_app()
    application.state.provider_manager = ProviderManager([provider])

    with TestClient(application) as client:
        first = client.get("/api/v1/market/BTC")
        second = client.get("/api/v1/market/BTC")

    assert first.status_code == 200
    assert first.json() == {
        "symbol": "BTC",
        "provider": "kiyotaka",
        "captured_at": "2026-03-29T16:00:00Z",
        "price": "123456.78",
        "funding_rate": "0.0001",
        "open_interest": "2000000000",
        "liquidation_volume": "30",
        "long_liquidation_volume": "10",
        "short_liquidation_volume": "20",
    }
    assert second.json() == first.json()
    assert calls == [4]


@pytest.mark.asyncio
async def test_quota_rejects_request_over_local_budget() -> None:
    """The local sliding window rejects an eleventh one-weight request before network I/O."""

    quota = SlidingWindowQuota(max_weight=1)
    await quota.reserve(weight=1)

    with pytest.raises(ProviderRateLimitError, match="budget"):
        await quota.reserve(weight=1)
