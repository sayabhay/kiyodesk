"""StrategyService — the public boundary of the Strategy Engine.

All application code (routes, journal integration, future engines) must import
from here.  Nothing outside the domain/ tree imports directly from ict/.
"""

from app.domain.strategy.ict.engine import StrategyEngine
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup


class StrategyService:
    """Stateless facade over the StrategyEngine.

    Replays the full bar history through a fresh StrategyEngine bar-by-bar,
    matching the kScript's sequential bar evaluation model.  The last TradeSetup
    detected (if any) is returned.

    For streaming / incremental bar feeds where state must persist across calls,
    instantiate StrategyEngine directly and reuse the same instance.
    """

    def evaluate(
        self,
        bars: list[Bar],
        htf_bars: list[Bar],
        symbol: str,
        config: StrategyConfig | None = None,
        timeframe: str | None = None,
    ) -> TradeSetup | None:
        """Evaluate the provided bar series and return a TradeSetup if found.

        Replays bars sequentially from oldest to newest.  Returns the most
        recent TradeSetup detected, or None if no setup was found at any point.

        Parameters
        ----------
        bars:      LTF bar series in chronological order (oldest first).
        htf_bars:  HTF bar series for the EMA trend filter.
        symbol:    Ticker symbol (e.g. "BTC").
        config:    Strategy configuration; defaults to StrategyConfig() if None.
        timeframe: Optional timeframe label attached to any produced TradeSetup.

        Returns
        -------
        The most recent TradeSetup if one was detected during replay, else None.
        """
        if len(bars) < 2:
            return None

        engine = StrategyEngine(config or StrategyConfig())
        last_setup: TradeSetup | None = None

        # Feed bars incrementally — each call sees bars[0..i], matching kScript
        # bar-by-bar execution where state accumulates across bars.
        for i in range(2, len(bars) + 1):
            result = engine.evaluate(bars[:i], htf_bars, symbol, timeframe)
            if result is not None:
                last_setup = result

        return last_setup
