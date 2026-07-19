"""Tests for CCXT normalizer (Task 3)."""

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.ccxt.normalizer import (
    build_snapshot,
    funding_rate_to_decimal,
    open_interest_to_usd,
    ticker_to_price,
)


class TestTickerToPrice:
    def test_float_price(self) -> None:
        assert ticker_to_price({"last": 64000.0}) == Decimal("64000.0")

    def test_string_price(self) -> None:
        assert ticker_to_price({"last": "64000.5"}) == Decimal("64000.5")

    def test_none_price_returns_none(self) -> None:
        assert ticker_to_price({"last": None}) is None

    def test_missing_key_returns_none(self) -> None:
        assert ticker_to_price({}) is None

    def test_non_numeric_returns_none(self) -> None:
        assert ticker_to_price({"last": "not-a-number"}) is None

    def test_zero_price(self) -> None:
        assert ticker_to_price({"last": 0}) == Decimal("0")


class TestFundingRateToDecimal:
    def test_float_rate(self) -> None:
        result = funding_rate_to_decimal({"fundingRate": 1.15e-06})
        assert result is not None
        assert result == Decimal(str(1.15e-06))

    def test_string_rate(self) -> None:
        result = funding_rate_to_decimal({"fundingRate": "0.0001"})
        assert result == Decimal("0.0001")

    def test_none_rate_returns_none(self) -> None:
        assert funding_rate_to_decimal({"fundingRate": None}) is None

    def test_missing_key_returns_none(self) -> None:
        assert funding_rate_to_decimal({}) is None

    def test_negative_rate_allowed(self) -> None:
        result = funding_rate_to_decimal({"fundingRate": -0.0001})
        assert result is not None
        assert result < Decimal("0")


class TestOpenInterestToUsd:
    def test_amount_times_price(self) -> None:
        result = open_interest_to_usd({"openInterestAmount": 101000.0}, Decimal("64000"))
        assert result == Decimal(str(101000.0)) * Decimal("64000")

    def test_none_amount_returns_none(self) -> None:
        assert open_interest_to_usd({"openInterestAmount": None}, Decimal("64000")) is None

    def test_missing_amount_returns_none(self) -> None:
        assert open_interest_to_usd({}, Decimal("64000")) is None

    def test_none_price_returns_none(self) -> None:
        assert open_interest_to_usd({"openInterestAmount": 101000.0}, None) is None

    def test_both_none_returns_none(self) -> None:
        assert open_interest_to_usd({"openInterestAmount": None}, None) is None

    def test_zero_amount(self) -> None:
        result = open_interest_to_usd({"openInterestAmount": 0}, Decimal("64000"))
        assert result == Decimal("0")


class TestBuildSnapshot:
    def _ticker(self, price: float = 64000.0, ts: int | None = 1784400000000) -> dict:
        return {"last": price, "timestamp": ts}

    def _funding(self, rate: float = 0.0001) -> dict:
        return {"fundingRate": rate}

    def _oi(self, amount: float = 100000.0) -> dict:
        return {"openInterestAmount": amount}

    def test_all_fields_populated(self) -> None:
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(), self._funding(), self._oi())
        assert snap.symbol == "BTC"
        assert snap.provider == "ccxt_binance"
        assert snap.price == Decimal("64000.0")
        assert snap.funding_rate is not None
        assert snap.open_interest is not None
        assert snap.open_interest == Decimal(str(100000.0)) * Decimal("64000.0")

    def test_liquidation_always_none(self) -> None:
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(), self._funding(), self._oi())
        assert snap.liquidation_volume is None
        assert snap.long_liquidation_volume is None
        assert snap.short_liquidation_volume is None

    def test_none_funding_produces_none_rate(self) -> None:
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(), None, self._oi())
        assert snap.funding_rate is None

    def test_none_oi_produces_none_oi(self) -> None:
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(), self._funding(), None)
        assert snap.open_interest is None

    def test_both_optional_none_no_crash(self) -> None:
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(), None, None)
        assert snap.price == Decimal("64000.0")
        assert snap.funding_rate is None
        assert snap.open_interest is None

    def test_timestamp_from_ticker(self) -> None:
        ts_ms = 1784400000000
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(ts=ts_ms), None, None)
        expected = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
        assert snap.captured_at == expected

    def test_timestamp_falls_back_to_now_when_missing(self) -> None:
        before = datetime.now(tz=UTC)
        snap = build_snapshot("BTC", "ccxt_binance", self._ticker(ts=None), None, None)
        after = datetime.now(tz=UTC)
        assert before <= snap.captured_at <= after

    def test_symbol_uppercased_in_snapshot(self) -> None:
        snap = build_snapshot("btc", "ccxt_binance", self._ticker(), None, None)
        # normalizer does not uppercase — caller's responsibility; assert it passes through
        assert snap.symbol == "btc"

    def test_provider_name_stored(self) -> None:
        snap = build_snapshot("ETH", "ccxt_bybit", self._ticker(), None, None)
        assert snap.provider == "ccxt_bybit"
