"""TradeSetup — the structured domain object produced by the Strategy Engine.

This is NOT a database model. It is a pure domain object that travels through
the application: Dashboard, Trade Journal, Confidence Engine, and (eventually)
the AI Assistant all consume TradeSetup instances.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.domain.strategy.models.config import StrategyConfig


class TradeSetup(BaseModel):
    """A structured trading opportunity produced by the Strategy Engine.

    Fields
    ------
    symbol          : Ticker symbol evaluated (e.g. "BTC").
    direction       : "long" or "short".
    entry           : Suggested entry price (close of the triggering bar).
    stop_loss       : Calculated stop-loss level.
    take_profit     : Calculated take-profit level.
    risk_reward     : Actual derived R:R = abs(tp - entry) / abs(entry - sl).
    timeframe       : Optional chart timeframe label (e.g. "15m").
    strategy        : Strategy name — always "ICT Pure OTE" for this engine.
    reasons         : Human-readable list of confluence factors that triggered
                      this setup (e.g. "Bullish BOS confirmed").
    warnings        : Non-fatal cautions about relaxed configuration
                      (e.g. "HTF filter disabled").
    swing_high      : Most recently confirmed swing high at time of setup.
    swing_low       : Most recently confirmed swing low at time of setup.
    ote_top         : Upper boundary of the active OTE zone.
    ote_bottom      : Lower boundary of the active OTE zone.
    leg_low         : Low of the measured move leg used to compute the zone.
    leg_high        : High of the measured move leg used to compute the zone.
    timestamp       : Timestamp of the triggering bar (UTC).
    config_snapshot : Immutable copy of the config used to produce this setup.
    """

    symbol: str
    direction: Literal["long", "short"]
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_reward: Decimal
    timeframe: str | None = None
    strategy: str = "ICT Pure OTE"
    reasons: list[str]
    warnings: list[str]
    swing_high: Decimal | None = None
    swing_low: Decimal | None = None
    ote_top: Decimal
    ote_bottom: Decimal
    leg_low: Decimal
    leg_high: Decimal
    timestamp: datetime
    config_snapshot: StrategyConfig
