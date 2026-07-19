"""CandleLoader — fetches real OHLCV candles from CCXT for the Strategy Engine.

This replaces the flat price-snapshot approach used in StrategyRuntime.
Real candles have distinct open/high/low/close values — required for swing
pivot detection, BOS detection, and OTE zone calculation in the ICT Pure OTE
strategy.

CCXT fetch_ohlcv returns rows in the format:
    [timestamp_ms, open, high, low, close, volume]

Each row is converted to a Bar dataclass with Decimal fields.
Bars are returned in chronological order (oldest first), matching the
kScript's bar series convention.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import ccxt.async_support as ccxt_async
from loguru import logger

from app.core.config import Settings
from app.domain.strategy.interfaces.bar import Bar
from app.providers.ccxt.exchange_factory import close_exchange, create_exchange
from app.providers.errors import ProviderResponseError


def _row_to_bar(row: list[object]) -> Bar:
    """Convert a single CCXT OHLCV row to a Bar.

    CCXT format: [timestamp_ms, open, high, low, close, volume]
    """
    try:
        ts_ms = float(row[0])  # type: ignore[arg-type]
        timestamp = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)

        def _dec(v: object) -> Decimal:
            try:
                return Decimal(str(v))
            except (InvalidOperation, TypeError):
                return Decimal("0")

        return Bar(
            timestamp=timestamp,
            open=_dec(row[1]),
            high=_dec(row[2]),
            low=_dec(row[3]),
            close=_dec(row[4]),
            volume=_dec(row[5]),
        )
    except Exception as exc:
        raise ProviderResponseError(f"CandleLoader: failed to parse OHLCV row {row!r}: {exc}") from exc


class CandleLoader:
    """Fetch OHLCV candles from CCXT and convert them to Bar objects.

    One instance is created per StrategyRuntime evaluation cycle.
    Exchange instances are created and closed per fetch call to avoid
    CCXT async event-loop lifetime issues.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_bars(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
    ) -> list[Bar]:
        """Fetch OHLCV candles and return them as Bar objects.

        Parameters
        ----------
        symbol:    KiyoDesk symbol (e.g. "BTC"). Resolved via ccxt_symbol_mapping.
        timeframe: CCXT timeframe string (e.g. "15m", "4h", "1d").
        limit:     Number of candles to fetch (most recent ``limit`` bars).

        Returns
        -------
        List of Bar objects in chronological order (oldest first).
        Empty list if the symbol is not in the symbol map.

        Raises
        ------
        ProviderResponseError on any CCXT fetch failure.
        """
        symbol_map = self._settings.ccxt_symbol_mapping
        ccxt_symbol = symbol_map.get(symbol.upper())
        if ccxt_symbol is None:
            logger.warning(
                "CandleLoader: symbol '{}' not in symbol map — skipping.", symbol
            )
            return []

        exchange: ccxt_async.Exchange = create_exchange(self._settings)
        try:
            logger.debug(
                "CandleLoader: fetching {} candles for {} {} via {}.",
                limit,
                symbol,
                timeframe,
                self._settings.ccxt_exchange,
            )
            raw: list[list[object]] = await exchange.fetch_ohlcv(
                ccxt_symbol, timeframe, limit=limit
            )
        except Exception as exc:
            raise ProviderResponseError(
                f"CandleLoader: fetch_ohlcv failed for {symbol} {timeframe}: {exc}"
            ) from exc
        finally:
            await close_exchange(exchange)

        bars = [_row_to_bar(row) for row in raw]
        # CCXT returns newest last — this matches our chronological convention.
        logger.debug(
            "CandleLoader: received {} bars for {} {}.", len(bars), symbol, timeframe
        )
        return bars
