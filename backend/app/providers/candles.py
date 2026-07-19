"""Binance Futures public kline (OHLCV) fetcher.

Provides real candlestick data for the Strategy Engine without requiring
any API key — Binance exposes historical klines on public endpoints.

Endpoint: GET https://fapi.binance.com/fapi/v1/klines
Response columns (index): open_time, open, high, low, close, volume, ...
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from loguru import logger

from app.domain.strategy.interfaces.bar import Bar

_BASE_URL = "https://fapi.binance.com"

# KiyoDesk symbol → Binance Futures instrument
_SYMBOL_MAP: dict[str, str] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
}


def _binance_symbol(symbol: str) -> str:
    """Convert an app-level symbol (e.g. 'BTC') to a Binance instrument (e.g. 'BTCUSDT')."""
    upper = symbol.upper()
    mapped = _SYMBOL_MAP.get(upper, upper)
    return mapped


def _parse_bar(raw: list) -> Bar:
    """Parse one Binance kline array into a Bar.

    Binance kline format:
      [0] open_time (ms), [1] open, [2] high, [3] low, [4] close, [5] volume, ...
    """
    open_time_ms: int = raw[0]
    timestamp = datetime.fromtimestamp(open_time_ms / 1000, tz=UTC)
    return Bar(
        timestamp=timestamp,
        open=Decimal(str(raw[1])),
        high=Decimal(str(raw[2])),
        low=Decimal(str(raw[3])),
        close=Decimal(str(raw[4])),
        volume=Decimal(str(raw[5])),
    )


async def fetch_candles(
    symbol: str,
    interval: str = "15m",
    limit: int = 200,
) -> list[Bar]:
    """Fetch OHLCV candlestick bars from Binance Futures (no API key required).

    Parameters
    ----------
    symbol:   KiyoDesk symbol, e.g. "BTC" or "ETH".
    interval: Binance interval string, e.g. "15m", "4h", "1d".
    limit:    Number of bars to fetch (max 1500 per Binance docs).

    Returns
    -------
    List of Bar objects in chronological order (oldest first).
    Raises httpx.HTTPError on network failure.
    """
    instrument = _binance_symbol(symbol)
    params = {"symbol": instrument, "interval": interval, "limit": limit}

    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0) as client:
        response = await client.get("/fapi/v1/klines", params=params)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Binance klines request failed: {} — {}", exc.response.status_code, symbol)
        raise

    raw_candles: list[list] = response.json()
    bars = [_parse_bar(c) for c in raw_candles]
    logger.debug(
        "fetch_candles: {} bars fetched for {} @ {} (oldest={}, newest={}).",
        len(bars),
        symbol,
        interval,
        bars[0].timestamp.isoformat() if bars else "n/a",
        bars[-1].timestamp.isoformat() if bars else "n/a",
    )
    return bars
