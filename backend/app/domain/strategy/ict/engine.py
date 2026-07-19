"""StrategyEngine — the orchestrator that wires all ICT Pure OTE modules together.

This is the single entry point for the Strategy Engine.  Callers feed it bars
bar-by-bar (or as a growing slice) and receive a TradeSetup when a valid setup
is detected, or None when no setup is present on the current bar.

Architecture
------------
    List[Bar] (LTF) + List[Bar] (HTF) + StrategyConfig
          ↓
    StrategyEngine.evaluate()
          ↓
      swing.detect_pivots()       → (swing_high, swing_low)
      bos.detect_bos()            → (bos_up, bos_down)
      htf_trend.evaluate_trend()  → (htf_bullish, htf_bearish)
      ote.update_zone()           → ZoneState  (stored on self)
      ote.check_tap()             → (confirm_bull, confirm_bear)
      risk.calculate_*_risk()     → RiskLevels | None
      → TradeSetup | None

Statefulness
------------
The engine is STATEFUL.  It holds a ZoneState that persists across calls,
matching the kScript's `persist` variables.  One StrategyEngine instance
must be created per (symbol, timeframe) pair and reused across consecutive
bar evaluations.

kScript fidelity notes
----------------------
- Processing order exactly matches the kScript evaluation sequence.
- longEnabled  = tradeDir != "Short Only"
- shortEnabled = tradeDir != "Long Only"
- On a confirmed tap the zone is immediately disarmed (waitingBull/Bear = False)
  so subsequent bars do not re-trigger the same zone.
"""

from app.domain.strategy.ict.bos import detect_bos
from app.domain.strategy.ict.htf_trend import evaluate_trend
from app.domain.strategy.ict.ote import ZoneState, check_tap, update_zone
from app.domain.strategy.ict.risk import calculate_bear_risk, calculate_bull_risk
from app.domain.strategy.ict.swing import detect_pivots
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup


class StrategyEngine:
    """Stateful ICT Pure OTE strategy evaluator.

    Parameters
    ----------
    config : StrategyConfig
        All configurable parameters.  Frozen at construction time.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self._config = config
        self._zone_state = ZoneState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        bars: list[Bar],
        htf_bars: list[Bar],
        symbol: str,
        timeframe: str | None = None,
    ) -> TradeSetup | None:
        """Evaluate the current bar and return a TradeSetup if one is detected.

        Parameters
        ----------
        bars:      LTF bar series in chronological order (oldest first).
                   Must contain at least 2 bars; returns None otherwise.
        htf_bars:  HTF bar series for the EMA trend filter.
        symbol:    Ticker symbol (e.g. "BTC").
        timeframe: Optional label (e.g. "15m") attached to any produced setup.

        Returns
        -------
        TradeSetup if a valid setup is detected on the current (last) bar,
        otherwise None.
        """
        cfg = self._config

        if len(bars) < 2:
            return None

        long_enabled = cfg.trade_dir != "Short Only"
        short_enabled = cfg.trade_dir != "Long Only"

        # 1. Swing pivot detection
        swing_high, swing_low = detect_pivots(bars, cfg.swing_len)

        # 2. Break of structure
        bos_up, bos_down = detect_bos(bars, swing_high, swing_low)

        # 3. HTF trend filter
        htf_bullish, htf_bearish = evaluate_trend(htf_bars, cfg)

        # 4. Update OTE zone state machine
        self._zone_state = update_zone(
            state=self._zone_state,
            bos_up=bos_up,
            bos_down=bos_down,
            swing_high=swing_high,
            swing_low=swing_low,
            current_bar=bars[-1],
            config=cfg,
            long_enabled=long_enabled,
            short_enabled=short_enabled,
            htf_bullish=htf_bullish,
            htf_bearish=htf_bearish,
        )

        # 5. Check for OTE tap on the current bar
        confirm_bull, confirm_bear = check_tap(self._zone_state, bars[-1], cfg)

        # 6. Bull setup
        if confirm_bull:
            setup = self._build_bull_setup(bars[-1], symbol, timeframe, swing_high, swing_low)
            if setup is not None:
                # Disarm the zone — kScript sets waitingBull = false after entry
                from dataclasses import replace

                self._zone_state = replace(self._zone_state, waiting_bull=False)
                return setup

        # 7. Bear setup
        if confirm_bear:
            setup = self._build_bear_setup(bars[-1], symbol, timeframe, swing_high, swing_low)
            if setup is not None:
                from dataclasses import replace

                self._zone_state = replace(self._zone_state, waiting_bear=False)
                return setup

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_bull_setup(
        self,
        bar: Bar,
        symbol: str,
        timeframe: str | None,
        swing_high: object,
        swing_low: object,
    ) -> TradeSetup | None:
        """Attempt to build a bull TradeSetup from the current zone state."""
        z = self._zone_state
        if (
            z.bull_leg_low is None
            or z.bull_leg_high is None
            or z.bull_sl is None
            or z.bull_ote_top is None
            or z.bull_ote_bottom is None
        ):
            return None

        risk = calculate_bull_risk(
            entry=bar.close,
            sl=z.bull_sl,
            leg_low=z.bull_leg_low,
            leg_high=z.bull_leg_high,
            config=self._config,
        )
        if risk is None:
            return None

        reasons, warnings = self._build_reasons_bull()

        return TradeSetup(
            symbol=symbol.upper(),
            direction="long",
            entry=risk.entry,
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit,
            risk_reward=risk.risk_reward,
            timeframe=timeframe,
            reasons=reasons,
            warnings=warnings,
            swing_high=z.bull_leg_high,
            swing_low=z.bull_leg_low,
            ote_top=z.bull_ote_top,
            ote_bottom=z.bull_ote_bottom,
            leg_low=z.bull_leg_low,
            leg_high=z.bull_leg_high,
            timestamp=bar.timestamp,
            config_snapshot=self._config,
        )

    def _build_bear_setup(
        self,
        bar: Bar,
        symbol: str,
        timeframe: str | None,
        swing_high: object,
        swing_low: object,
    ) -> TradeSetup | None:
        """Attempt to build a bear TradeSetup from the current zone state."""
        z = self._zone_state
        if (
            z.bear_leg_low is None
            or z.bear_leg_high is None
            or z.bear_sl is None
            or z.bear_ote_top is None
            or z.bear_ote_bottom is None
        ):
            return None

        risk = calculate_bear_risk(
            entry=bar.close,
            sl=z.bear_sl,
            leg_low=z.bear_leg_low,
            leg_high=z.bear_leg_high,
            config=self._config,
        )
        if risk is None:
            return None

        reasons, warnings = self._build_reasons_bear()

        return TradeSetup(
            symbol=symbol.upper(),
            direction="short",
            entry=risk.entry,
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit,
            risk_reward=risk.risk_reward,
            timeframe=timeframe,
            reasons=reasons,
            warnings=warnings,
            swing_high=z.bear_leg_high,
            swing_low=z.bear_leg_low,
            ote_top=z.bear_ote_top,
            ote_bottom=z.bear_ote_bottom,
            leg_low=z.bear_leg_low,
            leg_high=z.bear_leg_high,
            timestamp=bar.timestamp,
            config_snapshot=self._config,
        )

    def _build_reasons_bull(self) -> tuple[list[str], list[str]]:
        """Return (reasons, warnings) for a bull setup."""
        cfg = self._config
        z = self._zone_state

        reasons: list[str] = [
            "Bullish BOS confirmed",
            (
                f"Price tapped OTE zone "
                f"{float(cfg.ote_start) * 100:.1f}%–{float(cfg.ote_end) * 100:.1f}% "
                f"retracement"
            ),
        ]
        if z.bull_leg_low is not None and z.bull_leg_high is not None:
            reasons.append(f"Leg: {z.bull_leg_low} → {z.bull_leg_high}")

        warnings: list[str] = []
        if not cfg.use_htf_trend:
            warnings.append("HTF trend filter disabled")
        if not cfg.require_close_back:
            warnings.append("require_close_back disabled — wick entry accepted")
        if cfg.tp_mode == "Fib Extension":
            reasons.append(f"TP: Fib extension {float(cfg.fib_ext):.1f}×")
        else:
            reasons.append(f"TP: Fixed RR {float(cfg.rr_ratio):.1f}R")

        return reasons, warnings

    def _build_reasons_bear(self) -> tuple[list[str], list[str]]:
        """Return (reasons, warnings) for a bear setup."""
        cfg = self._config
        z = self._zone_state

        reasons: list[str] = [
            "Bearish BOS confirmed",
            (
                f"Price tapped OTE zone "
                f"{float(cfg.ote_start) * 100:.1f}%–{float(cfg.ote_end) * 100:.1f}% "
                f"retracement"
            ),
        ]
        if z.bear_leg_low is not None and z.bear_leg_high is not None:
            reasons.append(f"Leg: {z.bear_leg_high} → {z.bear_leg_low}")

        warnings: list[str] = []
        if not cfg.use_htf_trend:
            warnings.append("HTF trend filter disabled")
        if not cfg.require_close_back:
            warnings.append("require_close_back disabled — wick entry accepted")
        if cfg.tp_mode == "Fib Extension":
            reasons.append(f"TP: Fib extension {float(cfg.fib_ext):.1f}×")
        else:
            reasons.append(f"TP: Fixed RR {float(cfg.rr_ratio):.1f}R")

        return reasons, warnings
