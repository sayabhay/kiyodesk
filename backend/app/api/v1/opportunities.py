"""Trade Opportunity endpoints.

GET  /api/v1/opportunities           — list all (filterable by symbol, status)
GET  /api/v1/opportunities/active    — list ACTIVE only
GET  /api/v1/opportunities/{id}      — get one by id
POST /api/v1/opportunities/{id}/accept — accept → create Trade Journal entry
POST /api/v1/opportunities/{id}/reject — reject → lifecycle only, no trade
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_provider_manager
from app.database.session import get_session
from app.models.trade_opportunity import OpportunityStatus
from app.providers.manager import ProviderManager
from app.repositories.opportunity_repository import OpportunityRepository
from app.repositories.trade_repository import TradeRepository
from app.runtime.lifecycle_manager import InvalidTransitionError, LifecycleManager
from app.schemas.opportunity import (
    AcceptOpportunityRequest,
    OpportunityResponse,
    RejectOpportunityRequest,
)
from app.schemas.trade import CreateTradeRequest, TradeDirection
from app.services.trade_service import TradeService

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _to_response(opp: object) -> OpportunityResponse:
    return OpportunityResponse.model_validate(opp)


@router.get("", response_model=list[OpportunityResponse])
async def list_opportunities(
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[OpportunityResponse]:
    """List all trade opportunities, optionally filtered by symbol and/or status."""
    repo = OpportunityRepository(session)
    opps = await repo.list_all(symbol=symbol, status=status, limit=limit)
    return [_to_response(o) for o in opps]


@router.get("/recent", response_model=list[OpportunityResponse])
async def list_recent_opportunities(
    since: str | None = Query(
        default=None,
        description="ISO 8601 datetime — return only opportunities created after this time.",
    ),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    session: AsyncSession = Depends(get_session),
) -> list[OpportunityResponse]:
    """Return ACTIVE opportunities created after ``since``.

    Designed for efficient Signal Center polling — returns only new records
    rather than the full active list.

    If ``since`` is omitted the endpoint defaults to the last hour, acting as
    a safe fallback that avoids returning the entire history.
    """
    from datetime import UTC, datetime, timedelta

    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid 'since' datetime: {since!r}. Expected ISO 8601 format.",
            ) from exc
    else:
        since_dt = datetime.now(tz=UTC) - timedelta(hours=1)

    repo = OpportunityRepository(session)
    opps = await repo.list_since(since=since_dt, symbol=symbol)
    return [_to_response(o) for o in opps]


@router.get("/active", response_model=list[OpportunityResponse])
async def list_active_opportunities(
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    session: AsyncSession = Depends(get_session),
) -> list[OpportunityResponse]:
    """List all ACTIVE trade opportunities."""
    repo = OpportunityRepository(session)
    opps = await repo.list_active(symbol=symbol)
    return [_to_response(o) for o in opps]


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: int,
    session: AsyncSession = Depends(get_session),
) -> OpportunityResponse:
    """Return one opportunity by id."""
    repo = OpportunityRepository(session)
    opp = await repo.get(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found.",
        )
    return _to_response(opp)


@router.post("/{opportunity_id}/accept", response_model=OpportunityResponse)
async def accept_opportunity(
    opportunity_id: int,
    _request: AcceptOpportunityRequest = AcceptOpportunityRequest(),
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> OpportunityResponse:
    """Accept an opportunity: create a Trade Journal entry and mark as TAKEN.

    The Trade Journal entry is created automatically from the opportunity fields.
    The Strategy Engine is not involved — it already did its work.
    """
    opp_repo = OpportunityRepository(session)
    opp = await opp_repo.get(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found.",
        )
    if opp.status != OpportunityStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Opportunity is not ACTIVE (current status: {opp.status}).",
        )

    # Create a Trade Journal record via TradeService.
    trade_request = CreateTradeRequest(
        symbol=opp.symbol,
        direction=TradeDirection(opp.direction),
        entry_price=opp.entry,
        stop_loss=opp.stop_loss,
        take_profit=opp.take_profit,
        timeframe=opp.timeframe,
        notes=f"Accepted from opportunity #{opp.id}. Strategy: {opp.strategy}.",
        strategy_version=opp.strategy or "ICT Pure OTE",
    )
    trade_service = TradeService(TradeRepository(session), providers)
    trade_response = await trade_service.create(trade_request)

    # Transition opportunity: ACTIVE → TAKEN.
    try:
        LifecycleManager().accept(opp, trade_id=trade_response.id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    updated = await opp_repo.update(opp)
    return _to_response(updated)


@router.post("/{opportunity_id}/reject", response_model=OpportunityResponse)
async def reject_opportunity(
    opportunity_id: int,
    request: RejectOpportunityRequest = RejectOpportunityRequest(),
    session: AsyncSession = Depends(get_session),
) -> OpportunityResponse:
    """Reject an opportunity: lifecycle transition only, no trade is created."""
    opp_repo = OpportunityRepository(session)
    opp = await opp_repo.get(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found.",
        )

    try:
        LifecycleManager().reject(opp)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if request.notes:
        import json as _json

        meta = {}
        if opp.metadata_json:
            try:
                meta = _json.loads(opp.metadata_json)
            except _json.JSONDecodeError:
                pass
        meta["rejection_notes"] = request.notes
        opp.metadata_json = _json.dumps(meta)

    updated = await opp_repo.update(opp)
    return _to_response(updated)
