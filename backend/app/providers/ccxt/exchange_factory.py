"""CCXT exchange instance factory.

Creates ccxt.async_support exchange instances from Settings.
Exchange instances are created per-request (not shared) to avoid event
loop lifecycle issues with CCXT's internal async connection state.

Supported exchanges and their required defaultType:
  binance  → as configured (default: future)
  bybit    → as configured (default: future)
  bitget   → as configured (default: future)
  okx      → swap (always — OKX uses "swap" not "future")
"""

import ccxt.async_support as ccxt_async

from app.core.config import Settings
from app.providers.errors import ProviderConfigurationError

_SUPPORTED_EXCHANGES: frozenset[str] = frozenset({"binance", "bybit", "bitget", "okx"})
_OKX_MARKET_TYPE = "swap"


def create_exchange(settings: Settings) -> ccxt_async.Exchange:
    """Return a new configured CCXT exchange instance.

    Parameters
    ----------
    settings: Application settings carrying ccxt_exchange, ccxt_market_type,
              and optional ccxt_api_key / ccxt_api_secret.

    Raises
    ------
    ProviderConfigurationError if the exchange name is not supported.
    """
    exchange_id = settings.ccxt_exchange.lower()
    if exchange_id not in _SUPPORTED_EXCHANGES:
        raise ProviderConfigurationError(
            f"CCXT exchange '{exchange_id}' is not supported. "
            f"Supported: {sorted(_SUPPORTED_EXCHANGES)}."
        )

    # OKX requires "swap"; all others use the configured market type.
    market_type = _OKX_MARKET_TYPE if exchange_id == "okx" else settings.ccxt_market_type

    config: dict[str, object] = {
        "options": {"defaultType": market_type},
        "enableRateLimit": True,
    }
    if settings.ccxt_api_key:
        config["apiKey"] = settings.ccxt_api_key
    if settings.ccxt_api_secret:
        config["secret"] = settings.ccxt_api_secret

    exchange_class = getattr(ccxt_async, exchange_id)
    return exchange_class(config)


async def close_exchange(exchange: ccxt_async.Exchange) -> None:
    """Gracefully close an exchange instance, suppressing any close errors."""
    try:
        await exchange.close()
    except Exception:
        pass
