"""Risk Engine — SL/TP/RR calculation faithful to the kScript exit logic.

kScript reference
-----------------
Bull entry guard:
    if (bars.close - bullSL > 0) { ... }   ← only enter if risk > 0

Bear entry guard:
    if (bearSL - bars.close > 0) { ... }   ← only enter if risk > 0

Bull TP:
    Fixed RR:       bars.close + (bars.close - bullSL) * rrRatio
    Fib Extension:  bullLegHigh + (bullLegHigh - bullLegLow) * fibExt

Bear TP:
    Fixed RR:       bars.close - (bearSL - bars.close) * rrRatio
    Fib Extension:  bearLegLow  - (bearLegHigh - bearLegLow) * fibExt

Design notes
------------
- Returns None when the risk guard fails (entry - sl <= 0 for bull;
  sl - entry <= 0 for bear).  The engine must skip this bar.
- risk_reward is the actual derived R:R for display/audit purposes:
      abs(tp - entry) / abs(entry - sl)
- All arithmetic stays in Decimal for precision.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.strategy.models.config import StrategyConfig


@dataclass(frozen=True)
class RiskLevels:
    """Calculated entry, stop-loss, take-profit, and risk-reward for one setup."""

    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_reward: Decimal


def calculate_bull_risk(
    entry: Decimal,
    sl: Decimal,
    leg_low: Decimal,
    leg_high: Decimal,
    config: StrategyConfig,
) -> RiskLevels | None:
    """Calculate risk levels for a bullish OTE entry.

    Returns None if the risk guard fails (entry must be strictly above SL).

    kScript guard:  if (bars.close - bullSL > 0) { ... }
    """
    risk = entry - sl
    if risk <= Decimal("0"):
        return None

    if config.tp_mode == "Fixed RR":
        # kScript: bars.close + (bars.close - bullSL) * rrRatio
        take_profit = entry + risk * config.rr_ratio
    else:
        # kScript: bullLegHigh + (bullLegHigh - bullLegLow) * fibExt
        take_profit = leg_high + (leg_high - leg_low) * config.fib_ext

    reward = take_profit - entry
    risk_reward = reward / risk

    return RiskLevels(
        entry=entry,
        stop_loss=sl,
        take_profit=take_profit,
        risk_reward=risk_reward,
    )


def calculate_bear_risk(
    entry: Decimal,
    sl: Decimal,
    leg_low: Decimal,
    leg_high: Decimal,
    config: StrategyConfig,
) -> RiskLevels | None:
    """Calculate risk levels for a bearish OTE entry.

    Returns None if the risk guard fails (SL must be strictly above entry).

    kScript guard:  if (bearSL - bars.close > 0) { ... }
    """
    risk = sl - entry
    if risk <= Decimal("0"):
        return None

    if config.tp_mode == "Fixed RR":
        # kScript: bars.close - (bearSL - bars.close) * rrRatio
        take_profit = entry - risk * config.rr_ratio
    else:
        # kScript: bearLegLow - (bearLegHigh - bearLegLow) * fibExt
        take_profit = leg_low - (leg_high - leg_low) * config.fib_ext

    reward = entry - take_profit
    risk_reward = reward / risk

    return RiskLevels(
        entry=entry,
        stop_loss=sl,
        take_profit=take_profit,
        risk_reward=risk_reward,
    )
