"""Repository for normalized historical market observations."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import MarketData
from app.schemas.market import MarketSnapshot


class MarketDataRepository:
    """Persist distinct provider market snapshots for later charts and analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store_if_new(self, snapshot: MarketSnapshot) -> MarketData:
        """Save a snapshot once, avoiding duplicate rows caused by cached API responses."""

        existing = await self._session.scalar(
            select(MarketData).where(
                MarketData.symbol == snapshot.symbol,
                MarketData.provider == snapshot.provider,
                MarketData.captured_at == snapshot.captured_at,
            )
        )
        if existing is not None:
            return existing

        observation = MarketData(
            symbol=snapshot.symbol,
            exchange="BINANCE_FUTURES",
            provider=snapshot.provider,
            price=snapshot.price,
            open_interest=snapshot.open_interest,
            funding_rate=snapshot.funding_rate,
            liquidation_volume=snapshot.liquidation_volume,
            captured_at=snapshot.captured_at,
        )
        self._session.add(observation)
        await self._session.commit()
        await self._session.refresh(observation)
        return observation

    async def list_history(
        self,
        symbol: str,
        *,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
    ) -> tuple[list[MarketData], int]:
        """Return paginated history rows and total count for a symbol."""

        base = select(MarketData).where(MarketData.symbol == symbol.upper())
        if from_dt is not None:
            base = base.where(MarketData.captured_at >= from_dt)
        if to_dt is not None:
            base = base.where(MarketData.captured_at <= to_dt)

        count_query = select(func.count()).select_from(base.subquery())
        total: int = await self._session.scalar(count_query) or 0

        rows_query = base.order_by(MarketData.captured_at.asc()).limit(limit)
        rows = list(await self._session.scalars(rows_query))
        return rows, total
