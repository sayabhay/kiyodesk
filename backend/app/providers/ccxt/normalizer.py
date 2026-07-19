"""Normalize CCXT response dicts into MarketSnapshot objects.

Pure functions — no I/O, no state. All fields default to None on any
parse failure so the caller always receives a valid MarketSnapshot even
when individual data fields are unavailable.

Liquidation note
----------------
liquidation_volume is always None in the CCXT provider. CCXT 4.4.30 does
not implement fetchLiquidations for Binance, Bybit, or Bitget futures.
TODO: implement when CCXT adds support or via exchange-specific REST endpoints.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.market import MarketSnapshot


def ticker_to_price(ticker: dict[str, Any]) -> Decimal | None:
    """Extract the last trade price from a CCXT ticker dict."""
    try:
        return Decimal(str(ticker["last"]))
    except (KeyError, TypeError, InvalidOperation):
        return None


def funding_rate_to_decimal(funding: dict[str, Any]) -> Decimal | None:
    """Extract the funding rate from a CCXT funding rate dict."""
    try:
        return Decimal(str(funding["fundingRate"]))
    except (KeyError, TypeError, InvalidOperation):
        return None


def open_interest_to_usd(
    oi: dict[str, Any],
    price: Decimal | None,
) -> Decimal | None:
    """Convert CCXT openInterestAmount (base currency) to a USD value.

    CCXT 4.4.30 returns openInterestAmount in base currency (e.g. BTC).
    openInterestValue is not populated by Binance in this version, so USD
    value is computed as: openInterestAmount × current_price.

    Returns None when either input is unavailable.
    """
    if price is None:
        return None
    try:
        amount = oi.get("openInterestAmount")
        if amount is None:
            return None
        return Decimal(str(amount)) * price
    except (TypeError, InvalidOperation):
        return None


def build_snapshot(
    symbol: str,
    provider_name: str,
    ticker: dict[str, Any],
    funding: dict[str, Any] | None,
    oi: dict[str, Any] | None,
) -> MarketSnapshot:
    """Assemble a MarketSnapshot from CCXT response dicts.

    Parameters
    ----------
    symbol:        KiyoDesk symbol (e.g. "BTC").
    provider_name: Provider name string (e.g. "ccxt_binance").
    ticker:        CCXT fetch_ticker response dict (required).
    funding:       CCXT fetch_funding_rate response dict, or None.
    oi:            CCXT fetch_open_interest response dict, or None.
    """
    price = ticker_to_price(ticker)
    funding_rate = funding_rate_to_decimal(funding) if funding is not None else None
    open_interest = open_interest_to_usd(oi, price) if oi is not None else None

    # Prefer exchange-provided timestamp (milliseconds epoch); fall back to now.
    ts_ms = ticker.get("timestamp")
    if ts_ms and isinstance(ts_ms, (int, float)):
        captured_at = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
    else:
        captured_at = datetime.now(tz=UTC)

    return MarketSnapshot(
        symbol=symbol,
        provider=provider_name,
        captured_at=captured_at,
        price=price,
        funding_rate=funding_rate,
        open_interest=open_interest,
        liquidation_volume=None,  # TODO: CCXT 4.4.30 limitation
        long_liquidation_volume=None,
        short_liquidation_volume=None,
    )
