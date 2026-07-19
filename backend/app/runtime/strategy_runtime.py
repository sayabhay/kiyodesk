"""StrategyRuntime — loads market history, runs the Strategy Engine, persists opportunities.

This is the only component allowed to connect:
    Market Data  →  Strategy Engine  →  Trade Opportunities

The Scheduler calls MarketListener (below) after each successful symbol refresh.
MarketListener delegates here.  The Scheduler itself has no business logic.
"""

from decimal import Decimal

from loguru import logger

from app.core.config import Settings
from app.database.session import AsyncSessionLocal
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.services.strategy_service import StrategyService
from app.models.market_data import MarketData
from app.models.trade_opportunity import TradeOpportunity
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.deduplicator import Deduplicator
from app.runtime.opportunity_manager import OpportunityManager

_ZERO = Decimal("0")


def _market_data_to_bar(row: MarketData) -> Bar:
    """Convert a MarketData snapshot to a Bar.

    MarketData stores a single price point per capture, not candlestick OHLC.
    We map all four price fields to the same value (open=high=low=close=price).
    Volume is zero — the strategy engine does not use volume for ICT Pure OTE.

    TODO (future sprint): replace with resampled OHLCV candles when a candle
    history endpoint is available from the Provider Engine.
    """
    price = row.price if row.price is not None else _ZERO
    return Bar(
        timestamp=row.captured_at,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=_ZERO,
    )


class StrategyRuntime:
    """Orchestrate market data loading, strategy evaluation, and opportunity persistence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def on_market_update(self, symbol: str) -> TradeOpportunity | None:
        """Evaluate the strategy for a symbol after a market data refresh.

        Steps:
        1. Load recent bar history from market_data table.
        2. Convert rows to Bar objects.
        3. Run StrategyService with default config (use_htf_trend=False until
           true HTF candles are available — TODO: enable when candle feed lands).
        4. If no setup detected, return None.
        5. Create or update a TradeOpportunity via OpportunityManager.

        Parameters
        ----------
        symbol: Ticker symbol that was just refreshed (e.g. "BTC").

        Returns
        -------
        The created or updated TradeOpportunity, or None if no setup was found.
        """
        async with AsyncSessionLocal() as session:
            market_repo = MarketDataRepository(session)

            # Load LTF history (last 200 bars)
            ltf_rows, _ = await market_repo.list_history(symbol, limit=200)
            if len(ltf_rows) < 2:
                logger.debug(
                    "StrategyRuntime: not enough bars for {} ({} rows).",
                    symbol,
                    len(ltf_rows),
                )
                return None

            ltf_bars = [_market_data_to_bar(r) for r in ltf_rows]

            # HTF bars: same symbol, last 100 rows.
            # TODO (Sprint 3+): resample to true higher-timeframe candles.
            htf_bars = ltf_bars[-100:]

            # Build strategy config.
            # use_htf_trend=False until proper HTF candles are available; the
            # HTF filter on single-price snapshots is not meaningful.
            config = StrategyConfig(use_htf_trend=False)

            # Run the strategy.
            service = StrategyService()
            setup = service.evaluate(
                bars=ltf_bars,
                htf_bars=htf_bars,
                symbol=symbol,
                config=config,
            )

            if setup is None:
                logger.debug("StrategyRuntime: no setup detected for {}.", symbol)
                return None

            logger.info(
                "StrategyRuntime: setup detected for {} — {} @ {}.",
                symbol,
                setup.direction,
                setup.entry,
            )

            # Persist opportunity.
            opp_repo = OpportunityRepository(session)
            manager = OpportunityManager(
                repository=opp_repo,
                deduplicator=Deduplicator(),
            )
            opportunity = await manager.create_or_update(setup)
            logger.info(
                "StrategyRuntime: opportunity {} ({}) for {} persisted.",
                opportunity.id,
                opportunity.status,
                symbol,
            )
            return opportunity
