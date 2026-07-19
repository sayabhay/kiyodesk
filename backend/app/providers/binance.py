"""Binance public REST API adapter — price, funding rate, and open interest."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.cache.memory import TtlCache
from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderResponseError
from app.schemas.market import MarketSnapshot


class BinanceProvider(MarketDataProvider):
    """Fetch a cached market snapshot from Binance public endpoints (no API key required)."""

    name = "binance"
    _base_url = "https://fapi.binance.com"
    _instrument_map = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

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
        """Binance public API requires no credentials — always available."""

        return True

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return price, funding rate, and open interest for BTC or ETH."""

        normalized = symbol.upper()
        raw_symbol = self._instrument_map.get(normalized)
        if raw_symbol is None:
            supported = ", ".join(self._instrument_map)
            raise ProviderResponseError(
                f"Unsupported symbol '{symbol}'. Supported symbols: {supported}."
            )

        return await self._cache.get_or_set(
            key=f"{self.name}:snapshot:{normalized}",
            ttl_seconds=self._settings.cache_seconds,
            factory=lambda: self._fetch_snapshot(normalized, raw_symbol),
        )

    async def _fetch_snapshot(self, symbol: str, raw_symbol: str) -> MarketSnapshot:
        """Fetch price, funding rate, and open interest concurrently."""

        ticker, funding, open_interest = await asyncio.gather(
            self._get(f"/fapi/v1/ticker/price?symbol={raw_symbol}"),
            self._get(f"/fapi/v1/premiumIndex?symbol={raw_symbol}"),
            self._get(f"/fapi/v1/openInterest?symbol={raw_symbol}"),
        )

        price = self._parse_decimal(ticker, "price", "price")
        funding_rate = self._parse_decimal(funding, "lastFundingRate", "funding rate")
        oi = self._parse_decimal(open_interest, "openInterest", "open interest")

        return MarketSnapshot(
            symbol=symbol,
            provider=self.name,
            captured_at=datetime.now(tz=UTC),
            price=price,
            funding_rate=funding_rate,
            open_interest=oi,
            liquidation_volume=None,
            long_liquidation_volume=None,
            short_liquidation_volume=None,
        )

    async def _get(self, path: str) -> dict[str, Any]:
        """Issue one GET request to the Binance Futures REST API."""

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.get(path)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ProviderResponseError(
                f"Binance request failed with HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise ProviderResponseError("Binance could not be reached.") from error

        result: dict[str, Any] = response.json()
        return result

    @staticmethod
    def _parse_decimal(payload: dict[str, Any], field: str, label: str) -> Decimal:
        """Extract a decimal value from a Binance response field."""

        try:
            return Decimal(str(payload[field]))
        except (KeyError, InvalidOperation, TypeError) as error:
            raise ProviderResponseError(f"Binance returned no usable {label} value.") from error
