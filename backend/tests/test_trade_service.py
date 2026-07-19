"""Trade journal service coverage without creating a real database record."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.models.trade import Trade
from app.models.trade_snapshot import TradeSnapshot
from app.providers.base import MarketDataProvider
from app.providers.manager import ProviderManager
from app.schemas.market import MarketSnapshot
from app.schemas.trade import CloseTradeRequest, CreateTradeRequest, TradeDirection
from app.services.trade_service import TradeClosed, TradeNotFound, TradeService


class FakeKiyotakaProvider(MarketDataProvider):
    """In-memory market provider used to test journal enrichment."""

    name = "kiyotaka"

    async def health(self) -> bool:
        """Report a healthy fake provider."""

        return True

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return deterministic market context for one manual journal entry."""

        return MarketSnapshot(
            symbol=symbol.upper(),
            provider=self.name,
            captured_at=datetime(2026, 7, 18, tzinfo=UTC),
            price=Decimal("64000"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("2000000"),
            liquidation_volume=Decimal("1000"),
        )


def _make_trade(
    *,
    trade_id: int = 1,
    direction: str = "long",
    entry_price: Decimal = Decimal("64000"),
    status: str = "open",
    exit_price: Decimal | None = None,
    profit_loss: Decimal | None = None,
    profit_loss_pct: Decimal | None = None,
    closed_at: datetime | None = None,
) -> Trade:
    """Build a Trade ORM stub with test defaults."""

    trade = Trade(
        symbol="BTC",
        direction=direction,
        entry_price=entry_price,
        status=status,
        exit_price=exit_price,
        profit_loss=profit_loss,
        profit_loss_pct=profit_loss_pct,
        closed_at=closed_at,
    )
    trade.id = trade_id
    trade.created_at = datetime(2026, 7, 18, tzinfo=UTC)
    return trade


class FakeTradeRepository:
    """Minimal repository double that records operations without database I/O."""

    def __init__(self, stored: Trade | None = None) -> None:
        self.snapshot: TradeSnapshot | None = None
        self._stored = stored

    async def create(self, trade: Trade, snapshot: TradeSnapshot) -> Trade:
        """Assign persistence values without any database I/O."""

        trade.id = 1
        trade.created_at = datetime(2026, 7, 18, tzinfo=UTC)
        self.snapshot = snapshot
        return trade

    async def get(self, trade_id: int) -> Trade | None:
        """Return the pre-loaded trade or None."""

        return self._stored

    async def list(self, symbol: str | None = None) -> list[Trade]:
        """Return no journal records."""

        return []

    async def close(
        self,
        trade: Trade,
        exit_price: object,
        profit_loss: object,
        profit_loss_pct: object,
        closed_at: datetime,
    ) -> Trade:
        """Apply close values to the trade stub."""

        trade.exit_price = exit_price  # type: ignore[assignment]
        trade.profit_loss = profit_loss  # type: ignore[assignment]
        trade.profit_loss_pct = profit_loss_pct  # type: ignore[assignment]
        trade.status = "closed"
        trade.closed_at = closed_at
        return trade


def _make_service(stored: Trade | None = None) -> TradeService:
    return TradeService(
        FakeTradeRepository(stored),  # type: ignore[arg-type]
        ProviderManager([FakeKiyotakaProvider()]),
    )


@pytest.mark.asyncio
async def test_manual_trade_is_enriched_with_market_snapshot() -> None:
    """The service persists a trade alongside its vendor-neutral entry context."""

    repo = FakeTradeRepository()
    service = TradeService(repo, ProviderManager([FakeKiyotakaProvider()]))  # type: ignore[arg-type]

    response = await service.create(
        CreateTradeRequest(
            symbol="btc",
            direction=TradeDirection.LONG,
            entry_price=Decimal("63900"),
            stop_loss=Decimal("63500"),
            take_profit=Decimal("64700"),
        )
    )

    assert response.id == 1
    assert response.symbol == "BTC"
    assert response.market_snapshot is not None
    assert response.market_snapshot.open_interest == Decimal("2000000")
    assert repo.snapshot is not None
    assert repo.snapshot.funding_rate == Decimal("0.0001")


@pytest.mark.asyncio
async def test_close_long_trade_calculates_profit() -> None:
    """Closing a long trade at a higher price yields positive P&L."""

    trade = _make_trade(direction="long", entry_price=Decimal("60000"))
    response = await _make_service(trade).close(1, CloseTradeRequest(exit_price=Decimal("63000")))

    assert response.status == "closed"
    assert response.exit_price == Decimal("63000")
    assert response.profit_loss == Decimal("3000")
    assert response.profit_loss_pct == Decimal("5.000000")
    assert response.closed_at is not None


@pytest.mark.asyncio
async def test_close_long_trade_calculates_loss() -> None:
    """Closing a long trade at a lower price yields negative P&L."""

    trade = _make_trade(direction="long", entry_price=Decimal("60000"))
    response = await _make_service(trade).close(1, CloseTradeRequest(exit_price=Decimal("57000")))

    assert response.profit_loss == Decimal("-3000")
    assert response.profit_loss_pct == Decimal("-5.000000")


@pytest.mark.asyncio
async def test_close_short_trade_calculates_profit() -> None:
    """Closing a short trade at a lower price yields positive P&L."""

    trade = _make_trade(direction="short", entry_price=Decimal("60000"))
    response = await _make_service(trade).close(1, CloseTradeRequest(exit_price=Decimal("57000")))

    assert response.profit_loss == Decimal("3000")
    assert response.profit_loss_pct == Decimal("5.000000")


@pytest.mark.asyncio
async def test_close_already_closed_trade_raises() -> None:
    """Attempting to close an already-closed trade raises TradeClosed."""

    trade = _make_trade(status="closed")
    with pytest.raises(TradeClosed):
        await _make_service(trade).close(1, CloseTradeRequest(exit_price=Decimal("65000")))


@pytest.mark.asyncio
async def test_close_nonexistent_trade_raises() -> None:
    """Attempting to close a trade that does not exist raises TradeNotFound."""

    with pytest.raises(TradeNotFound):
        await _make_service(None).close(99, CloseTradeRequest(exit_price=Decimal("65000")))
