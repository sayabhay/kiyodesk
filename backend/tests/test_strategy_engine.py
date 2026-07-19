"""Unit and integration tests for the StrategyEngine orchestrator (Task 7).

Synthetic bar construction strategy
------------------------------------
swing_len = 3 (kept small so tests are concise).

A minimal bull scenario needs:
  1. A clear swing low confirmed (bars[3] with low=90 — 3 bars each side).
  2. A clear swing high confirmed (bars[9] with high=110 — confirmed by bar[12]).
  3. A BOS bar: bar[-2].close <= swing_high, bar[-1].close > swing_high.
  4. Several neutral bars so the zone stays alive.
  5. An OTE-tap bar: low <= ote_top AND high >= ote_bottom.

All HTF bars are rising so the trend filter passes.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategy.ict.engine import StrategyEngine
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup

D = Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(
    close: str,
    high: str | None = None,
    low: str | None = None,
    ts_offset: int = 0,
) -> Bar:
    c = D(close)
    h = D(high) if high else c
    lo = D(low) if low else c
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=ts_offset),
        open=c,
        high=h,
        low=lo,
        close=c,
        volume=D("1000"),
    )


def _rising_htf(n: int = 60) -> list[Bar]:
    """60 monotonically rising HTF bars — ensures htf_bullish=True."""
    return [_bar(str(100 + i), ts_offset=i) for i in range(n)]


def _falling_htf(n: int = 60) -> list[Bar]:
    """60 monotonically falling HTF bars — ensures htf_bearish=True."""
    return [_bar(str(200 - i), ts_offset=i) for i in range(n)]


def _build_bull_scenario(swing_len: int = 3) -> list[Bar]:
    """Build a bar series that produces one bull BOS followed by an OTE tap.

    Timeline (swing_len=3):
      bars 0-2  : flat at 100 (left-wing of swing low)
      bar  3    : spike low=90  (swing low candidate)
      bars 4-9  : rising from 100 → 109 (right-wing + approach to swing high)
      bar  9    : high=110 (swing high candidate — confirmed after bar 12)
      bars 10-12: flat at 105  (right-wing of swing high; bar 12 is last confirmation bar)
      bar  13   : BOS bar — prior=105, current=111  (crosses above swing_high=110)
      bars 14-15: neutral at 105 (zone alive, price above SL=89.955)
      bar  16   : OTE tap — low dips into zone

    With leg_low=90, leg_high=110, ote_start=0.618, ote_end=0.79:
      ote_top    = 110 - 20*0.618 = 110 - 12.36 = 97.64
      ote_bottom = 110 - 20*0.79  = 110 - 15.80 = 94.20
      sl         = 90 * (1 - 0.05/100) = 89.955

    Bar 16 (tap): low=95, high=99  → low(95) <= ote_top(97.64) AND high(99) >= ote_bottom(94.20)
    Bar 16 close=97  → above SL(89.955), so setup produced.
    """
    bars: list[Bar] = []
    t = 0

    # bars 0-2: flat at 100
    for _ in range(3):
        bars.append(_bar("100", ts_offset=t))
        t += 1

    # bar 3: swing low spike
    bars.append(_bar("100", high="100", low="90", ts_offset=t))
    t += 1

    # bars 4-8: rising
    for i in range(5):
        price = str(100 + i)
        bars.append(_bar(price, ts_offset=t))
        t += 1

    # bar 9: swing high candidate (high=110)
    bars.append(_bar("105", high="110", low="104", ts_offset=t))
    t += 1

    # bars 10-12: right-wing of swing high (close < 110 to avoid early BOS)
    for _ in range(3):
        bars.append(_bar("105", ts_offset=t))
        t += 1

    # bar 13: BOS — prior close=105 <= swing_high=110; current close=111 > 110
    bars.append(_bar("111", ts_offset=t))
    t += 1

    # bars 14-15: neutral, zone stays alive (close > SL=89.955)
    for _ in range(2):
        bars.append(_bar("105", ts_offset=t))
        t += 1

    # bar 16: OTE tap — wick enters zone, close inside zone
    # ote_top=97.64, ote_bottom=94.20 → low=95 <= 97.64, high=99 >= 94.20
    bars.append(_bar("97", high="99", low="95", ts_offset=t))
    t += 1

    return bars


def _build_bear_scenario(swing_len: int = 3) -> list[Bar]:
    """Build a bar series that produces one bear BOS followed by an OTE tap.

    Timeline:
      bars 0-2  : flat at 110
      bar  3    : spike high=120 (swing high candidate)
      bars 4-9  : falling 110→105
      bar  9    : low=100 (swing low candidate, confirmed by bar 12)
      bars 10-12: flat at 105 (right-wing)
      bar  13   : BOS — prior=105 >= swing_low=100; current=99 < 100
      bars 14-15: neutral at 105
      bar  16   : OTE tap — wick rises into bear zone

    leg_low=100, leg_high=120, ote_start=0.618, ote_end=0.79:
      ote_bottom = 100 + 20*0.618 = 112.36
      ote_top    = 100 + 20*0.79  = 115.80
      sl         = 120 * 1.0005   = 120.06

    Bar 16 tap: high=113, low=108 → high(113) >= ote_bottom(112.36) AND low(108) <= ote_top(115.80)
    Bar 16 close=112 → below SL(120.06), so setup produced.
    """
    bars: list[Bar] = []
    t = 0

    for _ in range(3):
        bars.append(_bar("110", ts_offset=t))
        t += 1

    bars.append(_bar("110", high="120", low="110", ts_offset=t))
    t += 1

    for i in range(5):
        price = str(110 - i)
        bars.append(_bar(price, ts_offset=t))
        t += 1

    bars.append(_bar("105", high="106", low="100", ts_offset=t))
    t += 1

    for _ in range(3):
        bars.append(_bar("105", ts_offset=t))
        t += 1

    # BOS down
    bars.append(_bar("99", ts_offset=t))
    t += 1

    for _ in range(2):
        bars.append(_bar("105", ts_offset=t))
        t += 1

    # OTE tap
    bars.append(_bar("112", high="113", low="108", ts_offset=t))
    t += 1

    return bars


# ---------------------------------------------------------------------------
# Engine construction
# ---------------------------------------------------------------------------


class TestStrategyEngineConstruction:
    def test_engine_initialises_with_default_config(self) -> None:
        engine = StrategyEngine(StrategyConfig())
        assert engine is not None

    def test_engine_initialises_with_custom_config(self) -> None:
        config = StrategyConfig(swing_len=10, trade_dir="Long Only", use_htf_trend=False)
        engine = StrategyEngine(config)
        assert engine is not None

    def test_empty_bars_returns_none(self) -> None:
        engine = StrategyEngine(StrategyConfig(use_htf_trend=False))
        assert engine.evaluate([], [], "BTC") is None

    def test_single_bar_returns_none(self) -> None:
        engine = StrategyEngine(StrategyConfig(use_htf_trend=False))
        assert engine.evaluate([_bar("100")], [], "BTC") is None


# ---------------------------------------------------------------------------
# Full bull integration scenario
# ---------------------------------------------------------------------------


class TestBullScenario:
    def _run(
        self,
        config: StrategyConfig | None = None,
        htf_bars: list[Bar] | None = None,
    ) -> TradeSetup | None:
        cfg = config or StrategyConfig(use_htf_trend=False, swing_len=3)
        htf = htf_bars if htf_bars is not None else []
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario(swing_len=cfg.swing_len)
        result: TradeSetup | None = None
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], htf, "BTC", "15m")
            if result is not None:
                break
        return result

    def test_bull_scenario_produces_setup(self) -> None:
        setup = self._run()
        assert setup is not None

    def test_setup_direction_is_long(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.direction == "long"

    def test_setup_symbol_is_uppercased(self) -> None:
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3)
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()
        result = None
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], [], "btc")
            if result is not None:
                break
        assert result is not None
        assert result.symbol == "BTC"

    def test_setup_strategy_name(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.strategy == "ICT Pure OTE"

    def test_setup_timeframe_propagated(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.timeframe == "15m"

    def test_setup_entry_is_close_of_tap_bar(self) -> None:
        setup = self._run()
        assert setup is not None
        # Tap bar close = 97
        assert setup.entry == D("97")

    def test_setup_stop_loss_below_entry(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.stop_loss < setup.entry

    def test_setup_take_profit_above_entry(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.take_profit > setup.entry

    def test_setup_risk_reward_matches_config(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.risk_reward == D("2.0")

    def test_setup_ote_levels_populated(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.ote_top is not None
        assert setup.ote_bottom is not None
        assert setup.ote_top > setup.ote_bottom

    def test_setup_leg_levels_populated(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.leg_low == D("90")
        assert setup.leg_high == D("110")

    def test_setup_reasons_non_empty(self) -> None:
        setup = self._run()
        assert setup is not None
        assert len(setup.reasons) >= 1
        assert any("Bullish BOS" in r for r in setup.reasons)

    def test_setup_config_snapshot_matches_config(self) -> None:
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3, rr_ratio=D("3.0"))
        setup = self._run(config=cfg)
        assert setup is not None
        assert setup.config_snapshot == cfg

    def test_setup_timestamp_is_set(self) -> None:
        setup = self._run()
        assert setup is not None
        assert isinstance(setup.timestamp, datetime)

    def test_zone_disarmed_after_entry(self) -> None:
        """After a setup fires the zone must be disarmed so it doesn't re-fire."""
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3)
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()
        setups: list[TradeSetup] = []
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], [], "BTC")
            if result is not None:
                setups.append(result)
        assert len(setups) == 1

    def test_htf_filter_enabled_rising_htf_produces_setup(self) -> None:
        cfg = StrategyConfig(use_htf_trend=True, swing_len=3, htf_ema_len=50)
        setup = self._run(config=cfg, htf_bars=_rising_htf(60))
        assert setup is not None

    def test_htf_filter_enabled_falling_htf_suppresses_bull_setup(self) -> None:
        """With a bearish HTF EMA, bull setups must be suppressed."""
        cfg = StrategyConfig(use_htf_trend=True, swing_len=3, htf_ema_len=50)
        setup = self._run(config=cfg, htf_bars=_falling_htf(60))
        assert setup is None


# ---------------------------------------------------------------------------
# Full bear integration scenario
# ---------------------------------------------------------------------------


class TestBearScenario:
    def _run(self, config: StrategyConfig | None = None) -> TradeSetup | None:
        cfg = config or StrategyConfig(use_htf_trend=False, swing_len=3)
        engine = StrategyEngine(cfg)
        bars = _build_bear_scenario(swing_len=cfg.swing_len)
        result: TradeSetup | None = None
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], [], "ETH", "1h")
            if result is not None:
                break
        return result

    def test_bear_scenario_produces_setup(self) -> None:
        assert self._run() is not None

    def test_setup_direction_is_short(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.direction == "short"

    def test_setup_stop_loss_above_entry(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.stop_loss > setup.entry

    def test_setup_take_profit_below_entry(self) -> None:
        setup = self._run()
        assert setup is not None
        assert setup.take_profit < setup.entry

    def test_setup_reasons_include_bearish_bos(self) -> None:
        setup = self._run()
        assert setup is not None
        assert any("Bearish BOS" in r for r in setup.reasons)


# ---------------------------------------------------------------------------
# Trade direction filtering
# ---------------------------------------------------------------------------


class TestTradeDirectionFilter:
    def test_long_only_suppresses_bear_setup(self) -> None:
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3, trade_dir="Long Only")
        engine = StrategyEngine(cfg)
        bars = _build_bear_scenario()
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], [], "BTC")
            assert result is None  # no bear setup should fire

    def test_short_only_suppresses_bull_setup(self) -> None:
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3, trade_dir="Short Only")
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], [], "BTC")
            assert result is None  # no bull setup should fire

    def test_both_allows_bull(self) -> None:
        cfg = StrategyConfig(use_htf_trend=False, swing_len=3, trade_dir="Both")
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()
        found = any(
            engine.evaluate(bars[:i], [], "BTC") is not None for i in range(2, len(bars) + 1)
        )
        assert found is True


# ---------------------------------------------------------------------------
# Zone invalidation before tap
# ---------------------------------------------------------------------------


class TestZoneInvalidationBeforeTap:
    def test_invalidation_before_tap_returns_none(self) -> None:
        """If the bull zone is invalidated before the tap bar, no bull setup fires.

        We use trade_dir='Long Only' so a close below swing_low cannot trigger
        a bear BOS that would produce a bear setup instead.

        The kill bar closes at 89 which is below bull_sl (90*0.9995≈89.955) but
        does not produce a new BOS crossover (prior close was 111 > swing_low=90,
        so bearish BOS requires prior >= swing_low which is satisfied — however
        with Long Only the bear zone is never armed).
        """
        cfg = StrategyConfig(
            use_htf_trend=False,
            swing_len=3,
            invalidate_on_close=True,
            trade_dir="Long Only",  # bear zone can never arm
        )
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()

        # Insert a bar that closes below the bull SL (≈89.955) after the BOS.
        # close=89 < 89.955 → bull zone invalidated.
        kill_bar = _bar("89", ts_offset=99)
        modified_bars = bars[:14] + [kill_bar] + bars[14:]

        result: TradeSetup | None = None
        for i in range(2, len(modified_bars) + 1):
            r = engine.evaluate(modified_bars[:i], [], "BTC")
            if r is not None:
                result = r
                break
        assert result is None

    def test_zone_survives_when_invalidation_disabled(self) -> None:
        """With invalidate_on_close=False the zone must survive a close below SL."""
        cfg = StrategyConfig(
            use_htf_trend=False,
            swing_len=3,
            invalidate_on_close=False,
            trade_dir="Long Only",
        )
        engine = StrategyEngine(cfg)
        bars = _build_bull_scenario()

        kill_bar = _bar("89", ts_offset=99)
        modified_bars = bars[:14] + [kill_bar] + bars[14:]

        result: TradeSetup | None = None
        for i in range(2, len(modified_bars) + 1):
            r = engine.evaluate(modified_bars[:i], [], "BTC")
            if r is not None:
                result = r
                break
        # Zone should still be alive and fire on the tap bar
        assert result is not None
        assert result.direction == "long"


# ---------------------------------------------------------------------------
# Inverted risk guard
# ---------------------------------------------------------------------------


class TestRiskGuard:
    def test_no_setup_when_entry_equals_sl(self) -> None:
        """If somehow entry == SL the risk guard must return None."""
        from dataclasses import replace
        from decimal import Decimal as D2

        from app.domain.strategy.ict.ote import ZoneState

        cfg = StrategyConfig(use_htf_trend=False, swing_len=3)
        engine = StrategyEngine(cfg)

        # Force a state where bull_sl == the tap bar close
        # by directly manipulating internal state (white-box test of the guard)
        engine._zone_state = replace(
            ZoneState(),
            waiting_bull=True,
            bull_leg_low=D2("90"),
            bull_leg_high=D2("110"),
            bull_ote_top=D2("97.64"),
            bull_ote_bottom=D2("94.20"),
            bull_sl=D2("97"),  # same as tap bar close → risk = 0
        )

        tap_bar = _bar("97", high="99", low="95")
        result = engine.evaluate([_bar("95"), tap_bar], [], "BTC")
        assert result is None
