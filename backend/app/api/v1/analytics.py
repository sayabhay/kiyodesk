"""Trade performance analytics endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.repositories.trade_repository import TradeRepository
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsResponse:
    """Return aggregate performance metrics for all closed journal trades.

    Pass ?symbol=BTC to scope metrics to a single symbol.
    """

    return await AnalyticsService(TradeRepository(session)).get_analytics(symbol=symbol)
