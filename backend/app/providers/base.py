"""Provider contract used by all market-data integrations."""

from abc import ABC, abstractmethod

from app.schemas.market import MarketSnapshot


class MarketDataProvider(ABC):
    """Stable interface that shields application code from vendor APIs."""

    name: str

    @abstractmethod
    async def health(self) -> bool:
        """Return whether the provider is configured and available."""

    @abstractmethod
    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return a normalized current market snapshot for a symbol."""
