"""KiyoDesk FastAPI application factory."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analytics, market, opportunities, providers, settings as settings_api, strategy, system, trades
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.database.session import AsyncSessionLocal, dispose_database, initialize_database
from app.models import ApiUsage, TradeOpportunity  # noqa: F401
from app.providers.base import MarketDataProvider
from app.providers.binance import BinanceProvider
from app.providers.ccxt.provider import CCXTProvider
from app.providers.coingecko import CoinGeckoProvider
from app.providers.kiyotaka import KiyotakaProvider
from app.providers.manager import ProviderManager
from app.runtime.market_listener import MarketListener
from app.runtime.strategy_runtime import StrategyRuntime
from app.runtime.trade_monitor import TradeMonitor
from app.scheduler.market_scheduler import MarketScheduler


def _build_provider_manager(settings: Settings) -> ProviderManager:
    """Instantiate providers in configured priority order.

    Any name matching "ccxt_{exchange}" is handled dynamically — the
    CCXTProvider's exchange is driven by the CCXT_EXCHANGE setting.
    """
    ccxt_name = f"ccxt_{settings.ccxt_exchange.lower()}"

    available: dict[str, Callable[[], MarketDataProvider]] = {
        "kiyotaka": lambda: KiyotakaProvider(settings),
        "binance": lambda: BinanceProvider(settings),
        "coingecko": lambda: CoinGeckoProvider(settings),
        ccxt_name: lambda: CCXTProvider(settings),
    }
    ordered = [available[name]() for name in settings.active_providers if name in available]
    return ProviderManager(ordered)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a KiyoDesk ASGI application."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await initialize_database()
        runtime = StrategyRuntime(active_settings)
        listener = MarketListener(runtime)
        trade_monitor = TradeMonitor(application.state.provider_manager, AsyncSessionLocal)
        scheduler = MarketScheduler(
            active_settings,
            application.state.provider_manager,
            on_refresh=listener,
            on_idle=trade_monitor.run,
        )
        application.state.market_scheduler = scheduler
        application.state.strategy_runtime = runtime
        scheduler.start()
        yield
        scheduler.shutdown()
        await dispose_database()

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description="Local-first crypto market intelligence platform.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.provider_manager = _build_provider_manager(active_settings)
    application.include_router(system.router, prefix=active_settings.api_v1_prefix)
    application.include_router(providers.router, prefix=active_settings.api_v1_prefix)
    application.include_router(market.router, prefix=active_settings.api_v1_prefix)
    application.include_router(trades.router, prefix=active_settings.api_v1_prefix)
    application.include_router(analytics.router, prefix=active_settings.api_v1_prefix)
    application.include_router(strategy.router, prefix=active_settings.api_v1_prefix)
    application.include_router(opportunities.router, prefix=active_settings.api_v1_prefix)
    application.include_router(settings_api.router, prefix=active_settings.api_v1_prefix)
    return application


app = create_app()
