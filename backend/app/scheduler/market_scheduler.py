"""Periodic market snapshot collection constrained by the provider quota layer.

Design constraint: the Scheduler is responsible ONLY for collecting market data.
It must never evaluate strategies, create opportunities, or run business logic.

After each successful symbol refresh the Scheduler calls the optional
``on_refresh`` callback (if registered) passing the symbol name.  All
business logic lives in the callback — not here.
"""

from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.database.session import AsyncSessionLocal
from app.providers.manager import ProviderManager
from app.repositories.market_data_repository import MarketDataRepository
from app.services.market_service import MarketService
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from loguru import logger

OnRefreshCallback = Callable[[str], Awaitable[None]]


class MarketScheduler:
    """Refresh configured market symbols into SQLite at a safe cadence."""

    def __init__(
        self,
        settings: Settings,
        providers: ProviderManager,
        on_refresh: OnRefreshCallback | None = None,
    ) -> None:
        self._settings = settings
        self._providers = providers
        self._on_refresh = on_refresh
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Start the periodic refresh job when scheduling is enabled."""

        if not self._settings.scheduler_enabled:
            return
        self._scheduler.add_job(
            self._refresh_all,
            trigger="interval",
            seconds=self._settings.market_refresh_seconds,
            id="market-refresh",
            replace_existing=True,
        )
        self._scheduler.start()

    def shutdown(self) -> None:
        """Stop scheduled jobs during application shutdown."""

        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def _refresh_all(self) -> None:
        """Refresh configured symbols, then notify the runtime callback.

        The Scheduler calls the on_refresh callback after each successful
        symbol refresh.  Callback errors are caught independently so one
        failing symbol does not block the others.
        """
        async with AsyncSessionLocal() as session:
            service = MarketService(self._providers, MarketDataRepository(session))
            for symbol in self._settings.scheduled_symbols:
                try:
                    await service.get_snapshot(symbol)
                except Exception as error:
                    logger.warning("Scheduled refresh for {} failed: {}", symbol, error)
                    continue  # skip callback if data collection failed

                if self._on_refresh is not None:
                    try:
                        await self._on_refresh(symbol)
                    except Exception as error:
                        logger.error("on_refresh callback failed for {}: {}", symbol, error)
