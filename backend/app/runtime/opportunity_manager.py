"""OpportunityManager — create or update TradeOpportunity records from TradeSetup objects.

This is the create-or-update logic that sits between the Strategy Engine output
and the persistence layer.  It delegates duplicate detection to Deduplicator and
persistence to OpportunityRepository.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategy.models.trade_setup import TradeSetup
from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.deduplicator import Deduplicator

_DEFAULT_TTL_HOURS = 4
_DEFAULT_TOLERANCE = Decimal("0.01")


class OpportunityManager:
    """Persist TradeSetup objects as TradeOpportunity records with deduplication."""

    def __init__(
        self,
        repository: OpportunityRepository,
        deduplicator: Deduplicator | None = None,
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> None:
        self._repository = repository
        self._deduplicator = deduplicator or Deduplicator(tolerance=_DEFAULT_TOLERANCE)
        self._ttl_hours = ttl_hours

    async def create_or_update(self, setup: TradeSetup) -> TradeOpportunity:
        """Create a new ACTIVE opportunity or update an existing one.

        Deduplication check:
          If an ACTIVE opportunity already exists for the same
          (strategy, symbol, timeframe, direction, entry ± tolerance),
          update its trade_setup_json and updated_at rather than inserting
          a new row.

        Parameters
        ----------
        setup: The TradeSetup produced by the Strategy Engine.

        Returns
        -------
        The created or updated TradeOpportunity.
        """
        setup_json = setup.model_dump_json()

        existing = await self._deduplicator.find_existing(setup, self._repository)
        if existing is not None:
            # Refresh the setup JSON on the existing record — the setup may have
            # slightly different levels if the bar that triggered it shifted.
            existing.trade_setup_json = setup_json
            return await self._repository.update(existing)

        now = datetime.now(tz=UTC)
        opportunity = TradeOpportunity(
            strategy=setup.strategy,
            strategy_version=setup.config_snapshot.model_dump().get("strategy_version"),
            symbol=setup.symbol,
            timeframe=setup.timeframe,
            direction=setup.direction,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit,
            risk_reward=setup.risk_reward,
            status=OpportunityStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(hours=self._ttl_hours),
            confidence=None,  # populated by Confidence Engine in v0.6
            market_regime=None,  # populated by Market Regime Engine in v0.7
            trade_setup_json=setup_json,
            entry_tolerance=self._deduplicator.tolerance,
        )
        return await self._repository.create(opportunity)
