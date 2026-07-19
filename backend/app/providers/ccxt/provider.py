"""CCXTProvider — MarketDataProvider backed by the CCXT library.

Provider name: "ccxt_{exchange_id}" — e.g. "ccxt_binance", "ccxt_bybit".
Plugs into ProviderManager like any other provider; no other layer is aware
of which exchange is providing data.

Data produced per snapshot:
  price           ✅  fetch_ticker → ticker["last"]
  funding_rate    ✅  fetch_funding_rate → funding["fundingRate"] (None if unsupported)
  open_interest   ✅  fetch_open_interest × price → USD (None if unsupported)
  liquidation_volume  ❌  None — CCXT 4.4.30 limitation (see normalizer.py)

Exchange instances are created per-request (not shared) to avoid CCXT
async event-loop lifetime issues. Funding and OI are fetched concurrently
with gather(); failures on either are silently converted to None so that
a missing secondary field never blocks the snapshot.
"""

import asyncio
from typing import Any

import ccxt.async_support as ccxt_async

from app.cache.memory import TtlCache
from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.ccxt.exchange_factory import close_exchange, create_exchange
from app.providers.ccxt.normalizer import build_snapshot
from app.providers.errors import ProviderRateLimitError, ProviderResponseError
from app.schemas.market import MarketSnapshot


class CCXTProvider(MarketDataProvider):
    """Fetch market snapshots from a configurable exchange via CCXT."""

    def __init__(self, settings: Settings, *, cache: TtlCache | None = None) -> None:
        self._settings = settings
        self._cache = cache or TtlCache()
        self.name = f"ccxt_{settings.ccxt_exchange.lower()}"

    async def health(self) -> bool:
        """Return True when the exchange loads its market list without error."""
        exchange = create_exchange(self._settings)
        try:
            await exchange.load_markets()
            return True
        except Exception:
            return False
        finally:
            await close_exchange(exchange)

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return a cached normalized snapshot for the given KiyoDesk symbol."""
        normalized = symbol.upper()
        return await self._cache.get_or_set(
            key=f"{self.name}:snapshot:{normalized}",
            ttl_seconds=self._settings.cache_seconds,
            factory=lambda: self._fetch_snapshot(normalized),
        )

    async def _fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        """Resolve symbol, open exchange, fetch all fields, and return snapshot."""
        symbol_map = self._settings.ccxt_symbol_mapping
        ccxt_symbol = symbol_map.get(symbol)
        if ccxt_symbol is None:
            raise ProviderResponseError(
                f"CCXT: '{symbol}' not in symbol map. "
                f"Configured symbols: {', '.join(symbol_map.keys()) or 'none'}."
            )

        exchange = create_exchange(self._settings)
        try:
            return await self._do_fetch(exchange, symbol, ccxt_symbol)
        finally:
            await close_exchange(exchange)

    async def _do_fetch(
        self,
        exchange: ccxt_async.Exchange,
        symbol: str,
        ccxt_symbol: str,
    ) -> MarketSnapshot:
        """Fetch ticker (required) and funding/OI (best-effort) concurrently."""

        # Ticker is mandatory — propagate failures as provider errors.
        try:
            ticker: dict[str, Any] = await exchange.fetch_ticker(ccxt_symbol)
        except ccxt_async.RateLimitExceeded as exc:
            raise ProviderRateLimitError(f"CCXT rate limit exceeded: {exc}") from exc
        except Exception as exc:
            raise ProviderResponseError(f"CCXT fetch_ticker failed: {exc}") from exc

        # Funding and OI are best-effort — failures produce None.
        async def _safe_funding() -> dict[str, Any] | None:
            try:
                result: dict[str, Any] = await exchange.fetch_funding_rate(ccxt_symbol)
                return result
            except Exception:
                return None

        async def _safe_oi() -> dict[str, Any] | None:
            try:
                result: dict[str, Any] = await exchange.fetch_open_interest(ccxt_symbol)
                return result
            except Exception:
                return None

        funding, oi = await asyncio.gather(_safe_funding(), _safe_oi())

        return build_snapshot(
            symbol=symbol,
            provider_name=self.name,
            ticker=ticker,
            funding=funding,
            oi=oi,
        )
