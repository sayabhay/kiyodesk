"""Repository for TradeOpportunity persistence operations."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity


class OpportunityRepository:
    """Encapsulate all persistence operations for TradeOpportunity records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Persist a new opportunity and return it with its assigned id."""
        self._session.add(opportunity)
        await self._session.commit()
        await self._session.refresh(opportunity)
        return opportunity

    async def get(self, opportunity_id: int) -> TradeOpportunity | None:
        """Return one opportunity by primary key, or None."""
        return await self._session.get(TradeOpportunity, opportunity_id)

    async def list_all(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[TradeOpportunity]:
        """Return opportunities in reverse-chronological order, optionally filtered."""
        query = select(TradeOpportunity).order_by(TradeOpportunity.created_at.desc())
        if symbol is not None:
            query = query.where(TradeOpportunity.symbol == symbol.upper())
        if status is not None:
            query = query.where(TradeOpportunity.status == status)
        query = query.limit(limit)
        result = await self._session.scalars(query)
        return list(result)

    async def list_since(
        self,
        since: datetime,
        symbol: str | None = None,
    ) -> list[TradeOpportunity]:
        """Return ACTIVE opportunities created after ``since``, newest first."""
        query = (
            select(TradeOpportunity)
            .where(
                TradeOpportunity.status == OpportunityStatus.ACTIVE,
                TradeOpportunity.created_at > since,
            )
            .order_by(TradeOpportunity.created_at.desc())
        )
        if symbol is not None:
            query = query.where(TradeOpportunity.symbol == symbol.upper())
        result = await self._session.scalars(query)
        return list(result)

    async def list_active(self, symbol: str | None = None) -> list[TradeOpportunity]:
        """Return all ACTIVE opportunities, optionally filtered by symbol."""
        return await self.list_all(symbol=symbol, status=OpportunityStatus.ACTIVE)

    async def update(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Flush pending changes, commit, and refresh the opportunity."""
        opportunity.updated_at = datetime.now(tz=UTC)
        await self._session.commit()
        await self._session.refresh(opportunity)
        return opportunity

    async def find_duplicate(
        self,
        strategy: str,
        symbol: str,
        timeframe: str | None,
        direction: str,
        entry: Decimal,
        tolerance: Decimal,
    ) -> TradeOpportunity | None:
        """Return an existing ACTIVE opportunity that matches within entry tolerance.

        Matches on strategy + symbol + timeframe + direction + entry ± tolerance.
        Returns the most recently created match, or None if no match exists.
        """
        query = (
            select(TradeOpportunity)
            .where(
                TradeOpportunity.strategy == strategy,
                TradeOpportunity.symbol == symbol.upper(),
                TradeOpportunity.direction == direction,
                TradeOpportunity.status == OpportunityStatus.ACTIVE,
                TradeOpportunity.entry >= entry - tolerance,
                TradeOpportunity.entry <= entry + tolerance,
            )
            .order_by(TradeOpportunity.created_at.desc())
            .limit(1)
        )

        # timeframe: both None or both equal
        if timeframe is not None:
            query = query.where(TradeOpportunity.timeframe == timeframe)
        else:
            query = query.where(TradeOpportunity.timeframe.is_(None))

        result: TradeOpportunity | None = await self._session.scalar(query)
        return result
