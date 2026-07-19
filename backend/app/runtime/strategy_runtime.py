"""StrategyRuntime — fetches real OHLCV candles, runs the Strategy Engine, persists opportunities.

This is the only component allowed to connect:
    Market Data  →  Strategy Engine  →  Trade Opportunities

The Scheduler calls MarketListener (below) after each successful symbol refresh.
MarketListener delegates here.  The Scheduler itself has no business logic.
"""

import asyncio

from loguru import logger

from app.core.config import Settings
from app.database.session import AsyncSessionLocal
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.services.strategy_service import StrategyService
from app.models.trade_opportunity import TradeOpportunity
from app.providers.candles import fetch_candles
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.deduplicator import Deduplicator
from app.runtime.opportunity_manager import OpportunityManager


class StrategyRuntime:
    """Orchestrate real OHLCV candle fetching, strategy evaluation, and opportunity persistence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def on_market_update(self, symbol: str) -> TradeOpportunity | None:
        """Evaluate the strategy for a symbol after a market data refresh.

        Steps:
        1. Fetch real OHLCV candles from Binance Futures (public, no API key).
           LTF: configured timeframe (default 15m), 200 bars.
           HTF: configured HTF timeframe (default 4h), 100 bars.
        2. Run StrategyService (bar-by-bar replay matching kScript behaviour).
        3. If no setup detected, return None.
        4. Create or update a TradeOpportunity via OpportunityManager.

        Parameters
        ----------
        symbol: Ticker symbol that was just refreshed (e.g. "BTC").

        Returns
        -------
        The created or updated TradeOpportunity, or None if no setup was found.
        """
        ltf_interval = self._settings.strategy_timeframe      # e.g. "15m"
        htf_interval = self._settings.strategy_htf_timeframe  # e.g. "4h"
        ltf_limit    = self._settings.strategy_candle_limit    # e.g. 200
        htf_limit    = 100

        try:
            ltf_bars, htf_bars = await asyncio.gather(
                fetch_candles(symbol, interval=ltf_interval, limit=ltf_limit),
                fetch_candles(symbol, interval=htf_interval, limit=htf_limit),
            )
        except Exception as exc:
            logger.warning(
                "StrategyRuntime: candle fetch failed for {} — {}. Skipping evaluation.",
                symbol,
                exc,
            )
            return None

        if len(ltf_bars) < 2:
            logger.debug(
                "StrategyRuntime: not enough LTF bars for {} ({}).",
                symbol,
                len(ltf_bars),
            )
            return None

        logger.debug(
            "StrategyRuntime: {} LTF bars + {} HTF bars fetched for {}.",
            len(ltf_bars),
            len(htf_bars),
            symbol,
        )

        # Full config — HTF trend filter is now meaningful with real 4h candles.
        config = StrategyConfig(use_htf_trend=len(htf_bars) >= 2)

        service = StrategyService()
        setup = service.evaluate(
            bars=ltf_bars,
            htf_bars=htf_bars,
            symbol=symbol,
            config=config,
            timeframe=ltf_interval,
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

        async with AsyncSessionLocal() as session:
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
