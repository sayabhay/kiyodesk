"""Business logic for manual trade journaling and market-context enrichment."""

from datetime import UTC, datetime
from decimal import Decimal

from app.models.trade import Trade
from app.models.trade_snapshot import TradeSnapshot
from app.providers.manager import ProviderManager
from app.repositories.trade_repository import TradeRepository
from app.schemas.market import MarketSnapshot
from app.schemas.trade import CloseTradeRequest, CreateTradeRequest, TradeDirection, TradeResponse


class TradeClosed(Exception):
    """Raised when attempting to close a trade that is already closed."""


class TradeNotFound(Exception):
    """Raised when a trade ID does not exist."""


class TradeService:
    """Create, close, and list journal trades without embedding business logic in routes."""

    def __init__(self, repository: TradeRepository, providers: ProviderManager) -> None:
        self._repository = repository
        self._providers = providers

    async def create(self, request: CreateTradeRequest) -> TradeResponse:
        """Capture the market context and persist a new manually-entered trade."""

        snapshot = await self._providers.get_snapshot_with_failover(request.symbol)
        trade = Trade(
            symbol=request.symbol.upper(),
            direction=request.direction.value,
            timeframe=request.timeframe,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            status="open",
            notes=request.notes,
            strategy_version=request.strategy_version,
        )
        persisted = await self._repository.create(trade, self._to_persistence_snapshot(snapshot))
        return self._to_response(persisted, snapshot)

    async def close(self, trade_id: int, request: CloseTradeRequest) -> TradeResponse:
        """Record the exit price, calculate P&L, and mark the trade closed."""

        trade = await self._repository.get(trade_id)
        if trade is None:
            raise TradeNotFound(trade_id)
        if trade.status == "closed":
            raise TradeClosed(trade_id)

        profit_loss, profit_loss_pct = self._calculate_pnl(
            direction=TradeDirection(trade.direction),
            entry_price=trade.entry_price,
            exit_price=request.exit_price,
        )
        closed = await self._repository.close(
            trade=trade,
            exit_price=request.exit_price,
            profit_loss=profit_loss,
            profit_loss_pct=profit_loss_pct,
            closed_at=datetime.now(tz=UTC),
        )
        return self._to_response(closed, None)

    async def list(self, symbol: str | None = None) -> list[TradeResponse]:
        """Return persisted trades; detailed snapshot retrieval follows in the next iteration."""

        trades = await self._repository.list(symbol=symbol)
        return [self._to_response(trade, None) for trade in trades]

    async def delete(self, trade_id: int) -> bool:
        """Delete a journal record and its associated market snapshot."""

        return await self._repository.delete(trade_id)

    @staticmethod
    def _calculate_pnl(
        direction: TradeDirection,
        entry_price: Decimal,
        exit_price: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Return (absolute P&L, percentage P&L) for a trade direction and price pair.

        Long:  profit when exit > entry  →  (exit - entry)
        Short: profit when exit < entry  →  (entry - exit)
        Percentage is relative to entry price, rounded to 6 decimal places.
        """

        if direction == TradeDirection.LONG:
            pnl = exit_price - entry_price
        else:
            pnl = entry_price - exit_price

        pnl_pct = (pnl / entry_price * Decimal("100")).quantize(Decimal("0.000001"))
        return pnl, pnl_pct

    @staticmethod
    def _to_persistence_snapshot(snapshot: MarketSnapshot) -> TradeSnapshot:
        """Translate the vendor-neutral snapshot into a relational model."""

        return TradeSnapshot(
            trade_id=0,
            price=snapshot.price,
            funding_rate=snapshot.funding_rate,
            open_interest=snapshot.open_interest,
            liquidations=snapshot.liquidation_volume,
            provider=snapshot.provider,
            captured_at=snapshot.captured_at,
        )

    @staticmethod
    def _to_response(trade: Trade, snapshot: MarketSnapshot | None) -> TradeResponse:
        """Map a persistence model to the stable public API response."""

        return TradeResponse(
            id=trade.id,
            symbol=trade.symbol,
            direction=TradeDirection(trade.direction),
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            exit_price=trade.exit_price,
            status=trade.status,
            profit_loss=trade.profit_loss,
            profit_loss_pct=trade.profit_loss_pct,
            timeframe=trade.timeframe,
            notes=trade.notes,
            strategy_version=trade.strategy_version,
            created_at=trade.created_at,
            closed_at=trade.closed_at,
            market_snapshot=snapshot,
        )
