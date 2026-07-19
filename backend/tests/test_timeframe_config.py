"""Tests for timeframe_config — MTF mapping, validation, and HTF resolution."""

import pytest

from app.runtime.timeframe_config import (
    DEFAULT_HTF_MAP,
    VALID_TIMEFRAMES,
    InvalidTimeframeError,
    resolve_htf,
)


# ---------------------------------------------------------------------------
# VALID_TIMEFRAMES completeness
# ---------------------------------------------------------------------------


class TestValidTimeframes:
    def test_contains_all_required_timeframes(self) -> None:
        required = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w", "1M"}
        assert required == set(VALID_TIMEFRAMES)

    def test_12h_is_first_class(self) -> None:
        """12H must be explicitly listed as a first-class timeframe (not derived)."""
        assert "12h" in VALID_TIMEFRAMES

    def test_1M_uppercase(self) -> None:
        """Monthly uses uppercase M (Binance Futures convention)."""
        assert "1M" in VALID_TIMEFRAMES
        assert "1m" in VALID_TIMEFRAMES   # minute is lowercase
        assert VALID_TIMEFRAMES.count("1m") == 1
        assert VALID_TIMEFRAMES.count("1M") == 1

    def test_no_duplicates(self) -> None:
        assert len(VALID_TIMEFRAMES) == len(set(VALID_TIMEFRAMES))

    def test_count_is_thirteen(self) -> None:
        assert len(VALID_TIMEFRAMES) == 13


# ---------------------------------------------------------------------------
# DEFAULT_HTF_MAP correctness
# ---------------------------------------------------------------------------


class TestDefaultHtfMap:
    def test_all_valid_timeframes_have_mapping(self) -> None:
        for tf in VALID_TIMEFRAMES:
            assert tf in DEFAULT_HTF_MAP, f"{tf!r} missing from DEFAULT_HTF_MAP"

    def test_all_htf_values_are_valid_timeframes(self) -> None:
        for ltf, htf in DEFAULT_HTF_MAP.items():
            assert htf in VALID_TIMEFRAMES, (
                f"DEFAULT_HTF_MAP[{ltf!r}] = {htf!r} is not a valid timeframe"
            )

    # --- spec-required mappings ---

    def test_1m_maps_to_5m(self) -> None:
        assert DEFAULT_HTF_MAP["1m"] == "5m"

    def test_3m_maps_to_15m(self) -> None:
        assert DEFAULT_HTF_MAP["3m"] == "15m"

    def test_5m_maps_to_15m(self) -> None:
        assert DEFAULT_HTF_MAP["5m"] == "15m"

    def test_15m_maps_to_1h(self) -> None:
        assert DEFAULT_HTF_MAP["15m"] == "1h"

    def test_30m_maps_to_4h(self) -> None:
        assert DEFAULT_HTF_MAP["30m"] == "4h"

    def test_1h_maps_to_4h(self) -> None:
        assert DEFAULT_HTF_MAP["1h"] == "4h"

    def test_2h_maps_to_12h(self) -> None:
        assert DEFAULT_HTF_MAP["2h"] == "12h"

    def test_4h_maps_to_12h(self) -> None:
        assert DEFAULT_HTF_MAP["4h"] == "12h"

    def test_6h_maps_to_1d(self) -> None:
        assert DEFAULT_HTF_MAP["6h"] == "1d"

    def test_12h_maps_to_1d(self) -> None:
        assert DEFAULT_HTF_MAP["12h"] == "1d"

    def test_1d_maps_to_1w(self) -> None:
        assert DEFAULT_HTF_MAP["1d"] == "1w"

    def test_1w_maps_to_1M(self) -> None:
        assert DEFAULT_HTF_MAP["1w"] == "1M"

    def test_1M_maps_to_itself(self) -> None:
        """Monthly has no higher TF — maps to itself so HTF filter is bypassed."""
        assert DEFAULT_HTF_MAP["1M"] == "1M"

    def test_12h_produces_1d_not_1w(self) -> None:
        """12H is a first-class timeframe with its own mapping (not grouped with 1d)."""
        assert DEFAULT_HTF_MAP["12h"] == "1d"
        assert DEFAULT_HTF_MAP["12h"] != "1w"


# ---------------------------------------------------------------------------
# resolve_htf — auto-resolution
# ---------------------------------------------------------------------------


class TestResolveHtfAutoResolution:
    def test_returns_default_htf_when_no_override(self) -> None:
        for ltf, expected_htf in DEFAULT_HTF_MAP.items():
            assert resolve_htf(ltf) == expected_htf

    def test_15m_resolves_to_1h(self) -> None:
        assert resolve_htf("15m") == "1h"

    def test_1h_resolves_to_4h(self) -> None:
        assert resolve_htf("1h") == "4h"

    def test_4h_resolves_to_12h(self) -> None:
        assert resolve_htf("4h") == "12h"

    def test_12h_resolves_to_1d(self) -> None:
        assert resolve_htf("12h") == "1d"

    def test_none_override_uses_default_map(self) -> None:
        assert resolve_htf("15m", override=None) == "1h"

    def test_1M_resolves_to_self(self) -> None:
        assert resolve_htf("1M") == "1M"


# ---------------------------------------------------------------------------
# resolve_htf — manual override
# ---------------------------------------------------------------------------


class TestResolveHtfOverride:
    def test_override_is_returned_verbatim(self) -> None:
        assert resolve_htf("15m", override="4h") == "4h"

    def test_override_can_be_any_valid_timeframe(self) -> None:
        for override_tf in VALID_TIMEFRAMES:
            result = resolve_htf("15m", override=override_tf)
            assert result == override_tf

    def test_override_ignores_default_mapping(self) -> None:
        # Default for 1h is 4h; override to 1d should win
        assert resolve_htf("1h", override="1d") == "1d"

    def test_override_with_12h(self) -> None:
        assert resolve_htf("1h", override="12h") == "12h"

    def test_override_with_1M(self) -> None:
        assert resolve_htf("1d", override="1M") == "1M"

    def test_override_same_as_ltf_allowed(self) -> None:
        """Caller may deliberately set HTF == LTF (disables HTF trend filter)."""
        assert resolve_htf("15m", override="15m") == "15m"


# ---------------------------------------------------------------------------
# resolve_htf — validation errors
# ---------------------------------------------------------------------------


class TestResolveHtfValidationErrors:
    def test_invalid_ltf_raises_invalid_timeframe_error(self) -> None:
        with pytest.raises(InvalidTimeframeError):
            resolve_htf("10m")

    def test_invalid_ltf_error_mentions_timeframe(self) -> None:
        with pytest.raises(InvalidTimeframeError, match="10m"):
            resolve_htf("10m")

    def test_invalid_override_raises_invalid_timeframe_error(self) -> None:
        with pytest.raises(InvalidTimeframeError):
            resolve_htf("15m", override="10m")

    def test_invalid_override_error_mentions_override_value(self) -> None:
        with pytest.raises(InvalidTimeframeError, match="10m"):
            resolve_htf("15m", override="10m")

    def test_empty_string_ltf_raises(self) -> None:
        with pytest.raises(InvalidTimeframeError):
            resolve_htf("")

    def test_uppercase_minute_raises(self) -> None:
        """'1M' is monthly; '1m' is minute. Wrong case must raise."""
        with pytest.raises(InvalidTimeframeError):
            resolve_htf("1H")  # should be "1h"

    def test_invalid_ltf_does_not_silently_fallback(self) -> None:
        """Misconfiguration must surface immediately — no silent defaults."""
        with pytest.raises((InvalidTimeframeError, ValueError)):
            resolve_htf("garbage")

    def test_valid_ltf_invalid_override_raises(self) -> None:
        with pytest.raises(InvalidTimeframeError):
            resolve_htf("1h", override="3H")  # should be "3m" or another valid tf


# ---------------------------------------------------------------------------
# InvalidTimeframeError
# ---------------------------------------------------------------------------


class TestInvalidTimeframeError:
    def test_is_value_error_subclass(self) -> None:
        err = InvalidTimeframeError("10m")
        assert isinstance(err, ValueError)

    def test_stores_timeframe_attribute(self) -> None:
        err = InvalidTimeframeError("10m")
        assert err.timeframe == "10m"

    def test_message_contains_invalid_value(self) -> None:
        err = InvalidTimeframeError("10m")
        assert "10m" in str(err)

    def test_message_contains_valid_list(self) -> None:
        err = InvalidTimeframeError("10m")
        # Should mention at least one known valid timeframe
        assert "15m" in str(err) or "1h" in str(err)

    def test_custom_context_appears_in_message(self) -> None:
        err = InvalidTimeframeError("10m", context="HTF override")
        assert "HTF override" in str(err)
