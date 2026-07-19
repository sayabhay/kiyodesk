"""Deduplicator — prevents creating duplicate ACTIVE TradeOpportunity records.

Duplicates are determined by:
    strategy + symbol + timeframe + direction + entry price (within tolerance)

If an ACTIVE opportunity already exists for the same setup, it is returned
so the caller can update it rather than inserting a new row.
"""

from decimal import Decimal

from app.domain.strategy.models.trade_setup import TradeSetup
from app.models.trade_opportunity import TradeOpportunity
from app.repositories.opportunity_repository import OpportunityRepository

_DEFAULT_TOLERANCE = Decimal("0.01")


class Deduplicator:
    """Check for existing ACTIVE opportunities before creating new ones."""

    def __init__(self, tolerance: Decimal = _DEFAULT_TOLERANCE) -> None:
        self._tolerance = tolerance

    async def find_existing(
        self,
        setup: TradeSetup,
        repository: OpportunityRepository,
    ) -> TradeOpportunity | None:
        """Return an existing ACTIVE opportunity that matches the setup, or None.

        Matching criteria:
        - strategy equals setup.strategy
        - symbol equals setup.symbol (case-insensitive)
        - timeframe equals setup.timeframe (None == None)
        - direction equals setup.direction
        - abs(entry - setup.entry) <= tolerance
        - status is ACTIVE

        Parameters
        ----------
        setup:      The incoming TradeSetup to check for duplicates.
        repository: OpportunityRepository scoped to the current session.

        Returns
        -------
        The most recently created matching ACTIVE opportunity, or None.
        """
        return await repository.find_duplicate(
            strategy=setup.strategy,
            symbol=setup.symbol,
            timeframe=setup.timeframe,
            direction=setup.direction,
            entry=setup.entry,
            tolerance=self._tolerance,
        )

    @property
    def tolerance(self) -> Decimal:
        """The entry price tolerance used for duplicate detection."""
        return self._tolerance
