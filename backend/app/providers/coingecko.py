"""CoinGecko REST API adapter — price-only fallback provider."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.cache.memory import TtlCache
from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderResponseError
from app.schemas.market import MarketSnapshot


class CoinGeckoProvider(MarketDataProvider):
    """Fetch a cached price snapshot from CoinGecko (free tier, no key required by default).

    CoinGecko free tier provides price data only. Funding rate, open interest,
    and liquidation fields will be None in the returned snapshot.
    Set COINGECKO_API_KEY in .env to use the Pro tier for higher rate limits.
    """

    name = "coingecko"
    _base_url = "https://api.coingecko.com"
    _coin_map = {"BTC": "bitcoin", "ETH": "ethereum"}

    def __init__(
        self,
        settings: Settings,
        *,
        cache: TtlCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._cache = cache or TtlCache()
        self._transport = transport

    async def health(self) -> bool:
        """CoinGecko free tier requires no credentials — always available."""

        return True

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return a price-only snapshot for BTC or ETH."""

        normalized = symbol.upper()
        coin_id = self._coin_map.get(normalized)
        if coin_id is None:
            supported = ", ".join(self._coin_map)
            raise ProviderResponseError(
                f"Unsupported symbol '{symbol}'. Supported symbols: {supported}."
            )

        return await self._cache.get_or_set(
            key=f"{self.name}:snapshot:{normalized}",
            ttl_seconds=self._settings.cache_seconds,
            factory=lambda: self._fetch_snapshot(normalized, coin_id),
        )

    async def _fetch_snapshot(self, symbol: str, coin_id: str) -> MarketSnapshot:
        """Fetch simple price from CoinGecko simple/price endpoint."""

        params = f"ids={coin_id}&vs_currencies=usd"
        headers: dict[str, str] = {}
        if self._settings.coingecko_api_key:
            headers["x-cg-pro-api-key"] = self._settings.coingecko_api_key

        payload = await self._get(f"/api/v3/simple/price?{params}", headers=headers)

        try:
            price = Decimal(str(payload[coin_id]["usd"]))
        except (KeyError, InvalidOperation, TypeError) as error:
            raise ProviderResponseError("CoinGecko returned no usable price value.") from error

        return MarketSnapshot(
            symbol=symbol,
            provider=self.name,
            captured_at=datetime.now(tz=UTC),
            price=price,
            funding_rate=None,
            open_interest=None,
            liquidation_volume=None,
            long_liquidation_volume=None,
            short_liquidation_volume=None,
        )

    async def _get(self, path: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Issue one GET request to the CoinGecko REST API."""

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers or {},
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.get(path)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ProviderResponseError(
                f"CoinGecko request failed with HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise ProviderResponseError("CoinGecko could not be reached.") from error

        result: dict[str, Any] = response.json()
        return result
