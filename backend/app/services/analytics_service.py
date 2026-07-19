"""Business logic for trade performance analytics."""

from app.analytics.calculator import compute_analytics
from app.repositories.trade_repository import TradeRepository
from app.schemas.analytics import AnalyticsResponse


class AnalyticsService:
    """Compute aggregate metrics from the trade journal."""

    def __init__(self, repository: TradeRepository) -> None:
        self._repository = repository

    async def get_analytics(self, symbol: str | None = None) -> AnalyticsResponse:
        """Return performance metrics, optionally scoped to one symbol."""

        trades = await self._repository.list(symbol=symbol)
        return compute_analytics(trades)
