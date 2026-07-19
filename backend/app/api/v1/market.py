"""Normalized live market-data endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_provider_manager
from app.database.session import get_session
from app.providers.errors import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from app.providers.manager import ProviderManager
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.market import MarketHistoryPoint, MarketHistoryResponse, MarketSnapshot
from app.services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/{symbol}/history", response_model=MarketHistoryResponse)
async def get_market_history(
    symbol: str,
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> MarketHistoryResponse:
    """Return stored historical market data points for a symbol.

    Supports optional time range filtering via ?from= and ?to= (ISO 8601).
    Maximum 1000 points per request.
    """

    repo = MarketDataRepository(session)
    rows, total = await repo.list_history(symbol, from_dt=from_dt, to_dt=to_dt, limit=limit)
    points = [
        MarketHistoryPoint(
            captured_at=row.captured_at,
            price=row.price,
            funding_rate=row.funding_rate,
            open_interest=row.open_interest,
            liquidation_volume=row.liquidation_volume,
            provider=row.provider,
        )
        for row in rows
    ]
    return MarketHistoryResponse(symbol=symbol.upper(), points=points, total=total)


@router.get("/{symbol}", response_model=MarketSnapshot)
async def get_market(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> MarketSnapshot:
    """Return a cached normalized market snapshot for BTC or ETH."""

    try:
        return await MarketService(providers, MarketDataRepository(session)).get_snapshot(symbol)
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except ProviderRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)
        ) from error
    except ProviderResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
