"""Repository for the trade journal and attached market snapshots."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.trade_snapshot import TradeSnapshot


class TradeRepository:
    """Encapsulate persistence operations for discretionary journal trades."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, trade: Trade, snapshot: TradeSnapshot) -> Trade:
        """Persist a trade and its entry-time snapshot atomically."""

        self._session.add(trade)
        await self._session.flush()
        snapshot.trade_id = trade.id
        self._session.add(snapshot)
        await self._session.commit()
        await self._session.refresh(trade)
        return trade

    async def get(self, trade_id: int) -> Trade | None:
        """Return a single trade by primary key, or None if not found."""

        return await self._session.get(Trade, trade_id)

    async def list(self, symbol: str | None = None) -> list[Trade]:
        """Return recent trades in reverse chronological order, optionally filtered by symbol."""

        query = select(Trade).order_by(Trade.created_at.desc())
        if symbol is not None:
            query = query.where(Trade.symbol == symbol.upper())
        result = await self._session.scalars(query)
        return list(result)

    async def list_open(self, symbol: str | None = None) -> list[Trade]:
        """Return all currently open trades, optionally filtered by symbol."""

        query = select(Trade).where(Trade.status == "open").order_by(Trade.created_at.desc())
        if symbol is not None:
            query = query.where(Trade.symbol == symbol.upper())
        result = await self._session.scalars(query)
        return list(result)

    async def close(
        self,
        trade: Trade,
        exit_price: object,
        profit_loss: object,
        profit_loss_pct: object,
        closed_at: datetime,
    ) -> Trade:
        """Persist exit values and mark the trade closed."""

        trade.exit_price = exit_price  # type: ignore[assignment]
        trade.profit_loss = profit_loss  # type: ignore[assignment]
        trade.profit_loss_pct = profit_loss_pct  # type: ignore[assignment]
        trade.status = "closed"
        trade.closed_at = closed_at
        await self._session.commit()
        await self._session.refresh(trade)
        return trade

    async def delete(self, trade_id: int) -> bool:
        """Remove one trade and its dependent entry-time snapshot."""

        trade = await self._session.get(Trade, trade_id)
        if trade is None:
            return False
        snapshots = await self._session.scalars(
            select(TradeSnapshot).where(TradeSnapshot.trade_id == trade_id)
        )
        for snapshot in snapshots:
            await self._session.delete(snapshot)
        await self._session.delete(trade)
        await self._session.commit()
        return True
