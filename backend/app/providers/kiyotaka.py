"""Kiyotaka Data API adapter for normalized single-exchange market snapshots."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import time
from typing import Any, cast

import httpx

from app.cache.memory import TtlCache
from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderConfigurationError, ProviderResponseError
from app.providers.quota import SlidingWindowQuota
from app.schemas.market import MarketSnapshot


class KiyotakaProvider(MarketDataProvider):
    """Fetch a cached market snapshot from Kiyotaka with local quota protection."""

    name = "kiyotaka"
    _instrument_map = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

    def __init__(
        self,
        settings: Settings,
        *,
        cache: TtlCache | None = None,
        quota: SlidingWindowQuota | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._cache = cache or TtlCache()
        self._quota = quota or SlidingWindowQuota(settings.kiyotaka_requests_per_minute)
        self._transport = transport

    async def health(self) -> bool:
        """Report configuration status without exposing API credentials."""

        return bool(self._settings.kiyotaka_api_key)

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return price, funding, open interest, and liquidations for BTC or ETH."""

        normalized_symbol = symbol.upper()
        raw_symbol = self._instrument_map.get(normalized_symbol)
        if raw_symbol is None:
            supported = ", ".join(self._instrument_map)
            raise ProviderResponseError(
                f"Unsupported symbol '{symbol}'. Supported symbols: {supported}."
            )
        if not self._settings.kiyotaka_api_key:
            raise ProviderConfigurationError("KIYOTAKA_API_KEY is not configured.")

        return await self._cache.get_or_set(
            key=f"{self.name}:snapshot:{normalized_symbol}",
            ttl_seconds=self._settings.cache_seconds,
            factory=lambda: self._fetch_snapshot(normalized_symbol, raw_symbol),
        )

    async def _fetch_snapshot(self, symbol: str, raw_symbol: str) -> MarketSnapshot:
        """Issue four 1x requests and normalize the latest values into one snapshot."""

        now = int(time())
        price, open_interest, funding, liquidations = await asyncio.gather(
            self._request_points(
                point_type="TRADE_SIDE_AGNOSTIC_AGG",
                raw_symbol=raw_symbol,
                from_timestamp=now - 3600,
                period=3600,
            ),
            self._request_points(
                point_type="OPEN_INTEREST_AGG",
                raw_symbol=raw_symbol,
                from_timestamp=now - 3600,
                period=3600,
                extra_params={"transform.normalize.quote": "USD"},
            ),
            self._request_points(
                point_type="FUNDING_RATE_AGG",
                raw_symbol=raw_symbol,
                from_timestamp=now - 28800,
                period=28800,
            ),
            self._request_points(
                point_type="LIQUIDATION_AGG",
                raw_symbol=raw_symbol,
                from_timestamp=now - 3600,
                period=3600,
                extra_params={"transform.normalize.quote": "USD"},
            ),
        )
        price_value, captured_at = self._parse_single_value(price, "close")
        open_interest_value, _ = self._parse_single_value(open_interest, "close")
        funding_value, _ = self._parse_single_value(funding, "rateClose")
        liquidation_values = self._parse_liquidations(liquidations)

        return MarketSnapshot(
            symbol=symbol,
            provider=self.name,
            captured_at=captured_at,
            price=price_value,
            open_interest=open_interest_value,
            funding_rate=funding_value,
            liquidation_volume=sum(liquidation_values.values(), start=Decimal("0")),
            long_liquidation_volume=liquidation_values.get("BUY"),
            short_liquidation_volume=liquidation_values.get("SELL"),
        )

    async def _request_points(
        self,
        *,
        point_type: str,
        raw_symbol: str,
        from_timestamp: int,
        period: int,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make one 1x Kiyotaka query after locally reserving its request weight."""

        await self._quota.reserve(weight=1)
        params: dict[str, str | int] = {
            "type": point_type,
            "exchange": "BINANCE_FUTURES",
            "rawSymbol": raw_symbol,
            "interval": "HOUR",
            "from": from_timestamp,
            "period": period,
            "sortDirection": "SORT_DIRECTION_DESC",
        }
        if extra_params:
            params.update(extra_params)
        headers = {"X-Kiyotaka-Key": self._settings.kiyotaka_api_key or ""}

        try:
            async with httpx.AsyncClient(
                base_url=self._settings.kiyotaka_base_url,
                headers=headers,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.get("/v1/points", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ProviderResponseError(
                f"Kiyotaka request failed with HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise ProviderResponseError("Kiyotaka could not be reached.") from error

        return cast(dict[str, Any], response.json())

    def _parse_single_value(self, payload: dict[str, Any], field: str) -> tuple[Decimal, datetime]:
        """Extract one latest numeric field and its timestamp from Kiyotaka's envelope."""

        try:
            point = payload["series"][0]["points"][0]["Point"]
            value = Decimal(str(point[field]))
            seconds = int(point["timestamp"]["s"])
        except (KeyError, IndexError, TypeError, ValueError, InvalidOperation) as error:
            raise ProviderResponseError(f"Kiyotaka returned no usable {field} value.") from error

        return value, datetime.fromtimestamp(seconds, tz=UTC)

    def _parse_liquidations(self, payload: dict[str, Any]) -> dict[str, Decimal]:
        """Extract latest USD liquidation volume by liquidation side."""

        values: dict[str, Decimal] = {}
        try:
            series = payload["series"]
            for entry in series:
                side = entry["id"]["side"]
                point = entry["points"][0]["Point"]
                values[side] = Decimal(str(point["liquidations"]))
        except (KeyError, IndexError, TypeError, ValueError, InvalidOperation) as error:
            raise ProviderResponseError(
                "Kiyotaka returned no usable liquidation values."
            ) from error

        if not values:
            raise ProviderResponseError("Kiyotaka returned no liquidation series.")
        return values
