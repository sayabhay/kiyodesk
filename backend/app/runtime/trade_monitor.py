"""Automatic open-trade monitoring and exit execution.

The TradeMonitor watches the journal for open trades and closes them when
market price crosses stop-loss or take-profit levels. When a closed trade is
linked to an existing opportunity, the corresponding opportunity is transitioned
from TAKEN → COMPLETED.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable

from app.providers.manager import ProviderManager
from app.repositories.opportunity_repository import OpportunityRepository
from app.repositories.trade_repository import TradeRepository
from app.runtime.lifecycle_manager import InvalidTransitionError, LifecycleManager
from app.services.trade_service import CloseTradeRequest, TradeService
from app.database.session import AsyncSessionLocal
from app.models.trade import Trade
from app.models.trade_opportunity import OpportunityStatus
from loguru import logger


class TradeMonitor:
    """Monitor open trades and close them automatically on price triggers."""

    def __init__(self, providers: ProviderManager, session_factory: Callable[[], object]) -> None:
        self._providers = providers
        self._session_factory = session_factory

    async def run(self) -> None:
        """Scan all open trades and close any that hit stop-loss or take-profit."""
        async with self._session_factory() as session:  # type: ignore[call-arg]
            trade_repo = TradeRepository(session)
            opp_repo = OpportunityRepository(session)
            open_trades = await trade_repo.list_open()
            if not open_trades:
                return

            for trade in open_trades:
                await self._process_trade(trade, session, trade_repo, opp_repo)

    async def _process_trade(
        self,
        trade: Trade,
        session,
        trade_repo: TradeRepository,
        opp_repo: OpportunityRepository,
    ) -> None:
        if trade.status != "open":
            return
        if trade.stop_loss is None and trade.take_profit is None:
            return

        try:
            snapshot = await self._providers.get_snapshot_with_failover(trade.symbol)
        except Exception as error:
            logger.warning(
                "TradeMonitor: failed to fetch market price for {}: {}",
                trade.symbol,
                error,
            )
            return

        price = snapshot.price
        if price is None:
            logger.warning(
                "TradeMonitor: market snapshot price missing for {}. Skipping.",
                trade.symbol,
            )
            return

        hit, reason = self._exit_triggered(trade, price)
        if not hit:
            return

        logger.info(
            "TradeMonitor: {} trade #{} hit {} at {}. Closing trade.",
            trade.direction,
            trade.id,
            reason,
            price,
        )

        trade_service = TradeService(trade_repo, self._providers)
        try:
            closed_trade = await trade_service.close(trade.id, CloseTradeRequest(exit_price=price))
        except Exception as error:
            logger.error(
                "TradeMonitor: failed to close trade #{}: {}",
                trade.id,
                error,
            )
            return

        opportunity = await opp_repo.get_by_trade_id(closed_trade.id)
        if opportunity is None:
            return

        if opportunity.status != OpportunityStatus.TAKEN:
            logger.debug(
                "TradeMonitor: linked opportunity #%s is not TAKEN (status=%s); skipping completion.",
                opportunity.id,
                opportunity.status,
            )
            return

        try:
            LifecycleManager().complete(opportunity)
            await opp_repo.update(opportunity)
            logger.info(
                "TradeMonitor: opportunity #%s marked as COMPLETED for trade #%s.",
                opportunity.id,
                closed_trade.id,
            )
        except InvalidTransitionError as error:
            logger.warning(
                "TradeMonitor: failed to complete opportunity #%s: %s",
                opportunity.id,
                error,
            )

    @staticmethod
    def _exit_triggered(trade: Trade, price: Decimal) -> tuple[bool, str]:
        if trade.direction == "long":
            if trade.take_profit is not None and price >= trade.take_profit:
                return True, "take_profit"
            if trade.stop_loss is not None and price <= trade.stop_loss:
                return True, "stop_loss"
        else:
            if trade.take_profit is not None and price <= trade.take_profit:
                return True, "take_profit"
            if trade.stop_loss is not None and price >= trade.stop_loss:
                return True, "stop_loss"
        return False, ""
