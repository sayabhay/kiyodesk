"""StrategyRuntime — fetches real OHLCV candles, runs the Strategy Engine, persists opportunities.

This is the only component allowed to connect:
    Candle Feed  →  Strategy Engine  →  Trade Opportunities

The Scheduler calls MarketListener (below) after each successful symbol refresh.
MarketListener delegates here.  The Scheduler itself has no business logic.

Multi-Timeframe design
----------------------
The execution timeframe (LTF) is configured via ``STRATEGY_TIMEFRAME`` (default
``15m``).  The HTF is resolved automatically from ``DEFAULT_HTF_MAP`` in
``timeframe_config.py`` unless ``STRATEGY_HTF_TIMEFRAME`` is explicitly set.

All timeframe strings are validated on startup against ``VALID_TIMEFRAMES``.
Actual HTF candles are always fetched from Binance Futures — the HTF is never
computed by resampling LTF bars.
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
from app.runtime.timeframe_config import InvalidTimeframeError, resolve_htf
from app.schemas.events import Event
from app.services.event_bus import event_bus


class StrategyRuntime:
    """Orchestrate real OHLCV candle fetching, strategy evaluation, and opportunity persistence.

    On each call to ``on_market_update`` the runtime:

    1. Resolves the HTF from the configured LTF (or uses the manual override).
    2. Fetches LTF and HTF candles concurrently from Binance Futures.
    3. Runs the ICT Pure OTE Strategy Engine (bar-by-bar replay).
    4. Persists or updates a ``TradeOpportunity`` if a setup is detected.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Resolve and validate timeframes once at construction time so
        # misconfiguration is surfaced immediately on startup.
        ltf = settings.strategy_timeframe
        htf_override = settings.strategy_htf_timeframe or None
        try:
            resolved_htf = resolve_htf(ltf, override=htf_override)
        except InvalidTimeframeError as exc:
            raise ValueError(
                f"StrategyRuntime: invalid timeframe configuration — {exc}"
            ) from exc

        self._ltf_interval: str = ltf
        self._htf_interval: str = resolved_htf
        self._ltf_limit: int = settings.strategy_candle_limit
        self._htf_limit: int = settings.strategy_htf_candle_limit

        if htf_override:
            logger.info(
                "StrategyRuntime: LTF={} HTF={} (manual override).",
                self._ltf_interval,
                self._htf_interval,
            )
        else:
            logger.info(
                "StrategyRuntime: LTF={} HTF={} (auto-resolved from default map).",
                self._ltf_interval,
                self._htf_interval,
            )

    @property
    def ltf_interval(self) -> str:
        """The configured LTF candle interval (e.g. ``'15m'``)."""
        return self._ltf_interval

    @property
    def htf_interval(self) -> str:
        """The resolved HTF candle interval (e.g. ``'1h'``)."""
        return self._htf_interval

    async def on_market_update(self, symbol: str) -> TradeOpportunity | None:
        """Evaluate the strategy for a symbol after a market data refresh.

        Steps:
        1. Fetch real OHLCV candles from Binance Futures (public, no API key).
           LTF: ``ltf_interval`` × ``ltf_limit`` bars (default 15m × 200).
           HTF: ``htf_interval`` × ``htf_limit`` bars (default auto × 100).
           Both fetches run concurrently.
        2. Run StrategyService (bar-by-bar replay matching kScript behaviour).
        3. If no setup detected, return None.
        4. Create or update a TradeOpportunity via OpportunityManager.

        Parameters
        ----------
        symbol:
            Ticker symbol that was just refreshed (e.g. ``"BTC"``).

        Returns
        -------
        The created or updated ``TradeOpportunity``, or ``None`` if no
        setup was found or candle fetch failed.
        """
        logger.debug(
            "StrategyRuntime: evaluating {} on LTF={} HTF={}.",
            symbol,
            self._ltf_interval,
            self._htf_interval,
        )

        try:
            ltf_bars, htf_bars = await asyncio.gather(
                fetch_candles(symbol, interval=self._ltf_interval, limit=self._ltf_limit),
                fetch_candles(symbol, interval=self._htf_interval, limit=self._htf_limit),
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
            "StrategyRuntime: {} LTF bars ({}) + {} HTF bars ({}) fetched for {}.",
            len(ltf_bars),
            self._ltf_interval,
            len(htf_bars),
            self._htf_interval,
            symbol,
        )

        # HTF trend filter is meaningful whenever real HTF bars are available.
        # When LTF == HTF (e.g. 1M execution timeframe) the filter is disabled
        # because a self-referencing trend check adds no signal.
        use_htf = len(htf_bars) >= 2 and self._ltf_interval != self._htf_interval
        config = StrategyConfig(use_htf_trend=use_htf)

        service = StrategyService()
        setup = service.evaluate(
            bars=ltf_bars,
            htf_bars=htf_bars,
            symbol=symbol,
            config=config,
            timeframe=self._ltf_interval,
        )

        if setup is None:
            logger.debug("StrategyRuntime: no setup detected for {}.", symbol)
            return None

        logger.info(
            "StrategyRuntime: setup detected for {} — {} @ {} (LTF={} HTF={}).",
            symbol,
            setup.direction,
            setup.entry,
            self._ltf_interval,
            self._htf_interval,
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

            # PR-6: Publish SignalCreated or SignalUpdated event
            # We determine if it's new by looking at the status and created_at/updated_at
            # but OpportunityManager handles the persistence logic.
            # For simplicity, we emit SignalCreated if created_at == updated_at
            event_type = "SignalCreated" if opportunity.created_at == opportunity.updated_at else "SignalUpdated"
            
            await event_bus.publish(Event(
                event_type=event_type,
                source="TradingRuntime",
                payload={
                    "opportunity_id": str(opportunity.id),
                    "symbol": opportunity.symbol,
                    "direction": opportunity.direction,
                    "status": opportunity.status,
                    "entry": float(opportunity.entry) if opportunity.entry else None,
                    "stop_loss": float(opportunity.stop_loss) if opportunity.stop_loss else None,
                    "take_profit": float(opportunity.take_profit) if opportunity.take_profit else None,
                }
            ))

            return opportunity
