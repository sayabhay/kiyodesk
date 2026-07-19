"""MarketListener — adapter that connects the Scheduler to the StrategyRuntime.

The Scheduler calls MarketListener.__call__(symbol) after each successful
market data refresh.  MarketListener delegates to StrategyRuntime and
absorbs any runtime errors so a strategy failure never blocks the Scheduler.

Design constraint: the Scheduler must never contain business logic.
MarketListener is the boundary that enforces this.
"""

from loguru import logger

from app.runtime.strategy_runtime import StrategyRuntime


class MarketListener:
    """Callable adapter registered with MarketScheduler as the post-refresh hook."""

    def __init__(self, runtime: StrategyRuntime) -> None:
        self._runtime = runtime

    async def __call__(self, symbol: str) -> None:
        """Invoke the strategy runtime for the refreshed symbol.

        Errors are logged and swallowed — a runtime failure must never
        prevent the scheduler from continuing its data collection cycle.
        """
        try:
            await self._runtime.on_market_update(symbol)
        except Exception as error:
            logger.error(
                "MarketListener: runtime error for {}: {}",
                symbol,
                error,
            )
