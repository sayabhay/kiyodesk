"""Registry and failover service for pluggable market data providers."""

from loguru import logger

from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderError, ProviderRateLimitError
from app.schemas.market import MarketSnapshot


class ProviderManager:
    """Own provider registration and automatic failover across registered providers.

    Providers are tried in the order they were registered. When a provider raises
    ProviderRateLimitError the manager immediately skips to the next provider.
    Any other ProviderError on a provider also triggers fallback so transient
    network failures do not block the request when alternatives are available.
    The last provider's exception propagates if all providers fail.
    """

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        self._ordered: list[MarketDataProvider] = providers
        self._by_name: dict[str, MarketDataProvider] = {p.name: p for p in providers}

    def names(self) -> list[str]:
        """Return registered provider names in registration order."""

        return [p.name for p in self._ordered]

    def get(self, name: str) -> MarketDataProvider:
        """Look up a registered provider by name."""

        try:
            return self._by_name[name]
        except KeyError as error:
            raise ValueError(f"Provider '{name}' is not registered.") from error

    async def get_snapshot_with_failover(self, symbol: str) -> MarketSnapshot:
        """Return a market snapshot using automatic provider failover.

        Iterates providers in registration order. Skips to the next provider on
        ProviderRateLimitError (quota exhausted) or any other ProviderError
        (network failure, bad response). Raises the last error if all fail.
        """

        last_error: ProviderError | None = None
        for provider in self._ordered:
            try:
                snapshot = await provider.get_market_snapshot(symbol)
                if last_error is not None:
                    logger.info(
                        "Failover: {} succeeded after earlier provider(s) failed.",
                        provider.name,
                    )
                return snapshot
            except ProviderRateLimitError as error:
                logger.warning(
                    "Provider {} hit quota limit for {}; trying next provider.",
                    provider.name,
                    symbol,
                )
                last_error = error
            except ProviderError as error:
                logger.warning(
                    "Provider {} failed for {}: {}; trying next provider.",
                    provider.name,
                    symbol,
                    error,
                )
                last_error = error

        raise last_error or ProviderError("No providers are registered.")

    async def statuses(self) -> dict[str, bool]:
        """Return health states for every registered provider in order."""

        return {p.name: await p.health() for p in self._ordered}
