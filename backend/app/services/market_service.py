"""Business logic for vendor-neutral live market requests."""

from app.providers.manager import ProviderManager
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.market import MarketSnapshot


class MarketService:
    """Retrieve normalized market data through the provider manager with failover."""

    def __init__(
        self,
        providers: ProviderManager,
        market_data_repository: MarketDataRepository | None = None,
    ) -> None:
        self._providers = providers
        self._market_data_repository = market_data_repository

    async def get_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return a snapshot using automatic provider failover."""

        snapshot = await self._providers.get_snapshot_with_failover(symbol)
        if self._market_data_repository is not None:
            await self._market_data_repository.store_if_new(snapshot)
        return snapshot
