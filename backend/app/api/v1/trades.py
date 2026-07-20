"""Manual trade journal endpoints."""

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
from app.repositories.trade_repository import TradeRepository
from app.schemas.trade import CloseTradeRequest, CreateTradeRequest, TradeResponse
from app.schemas.events import Event
from app.services.event_bus import event_bus
from app.services.trade_service import TradeClosed, TradeNotFound, TradeService

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(
    request: CreateTradeRequest,
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> TradeResponse:
    """Record a manually selected KScript trade with its market context."""

    try:
        trade = await TradeService(TradeRepository(session), providers).create(request)
        
        # PR-6: Publish TradeOpened event
        await event_bus.publish(Event(
            event_type="TradeOpened",
            source="TradesAPI",
            payload={
                "trade_id": str(trade.id),
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": float(trade.entry_price) if trade.entry_price else None,
            }
        ))
        
        return trade
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


@router.get("", response_model=list[TradeResponse])
async def list_trades(
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> list[TradeResponse]:
    """List recently journaled trades, optionally filtered by symbol."""

    return await TradeService(TradeRepository(session), providers).list(symbol=symbol)


@router.patch("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: int,
    request: CloseTradeRequest,
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> TradeResponse:
    """Close an open trade, record the exit price, and calculate P&L."""

    try:
        trade = await TradeService(TradeRepository(session), providers).close(trade_id, request)
        
        # PR-6: Publish ManualClose event
        await event_bus.publish(Event(
            event_type="ManualClose",
            source="TradesAPI",
            payload={
                "trade_id": str(trade.id),
                "symbol": trade.symbol,
                "exit_price": float(trade.exit_price) if trade.exit_price else None,
                "pnl": float(trade.pnl) if trade.pnl else None,
            }
        ))
        
        return trade
    except TradeNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found."
        ) from error
    except TradeClosed as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Trade is already closed."
        ) from error


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: int,
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> None:
    """Remove one journal trade and its dependent market snapshot."""

    deleted = await TradeService(TradeRepository(session), providers).delete(trade_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found.")
