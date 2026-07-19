"""LifecycleManager — owns all TradeOpportunity status transitions.

Valid transitions:
    ACTIVE → TAKEN        (user accepts the opportunity)
    ACTIVE → REJECTED     (user rejects the opportunity)
    ACTIVE → INVALIDATED  (strategy invalidates the setup)
    ACTIVE → EXPIRED      (TTL exceeded)
    TAKEN  → COMPLETED    (trade is closed with a result)

All transitions are pure in-memory mutations.
The caller is responsible for persisting via OpportunityRepository.update().
"""

from datetime import UTC, datetime

from app.models.trade_opportunity import OpportunityStatus, TradeOpportunity


class InvalidTransitionError(Exception):
    """Raised when an illegal status transition is attempted."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition from '{current}' to '{target}'.")
        self.current = current
        self.target = target


class LifecycleManager:
    """Apply status transitions to TradeOpportunity objects.

    Methods mutate the opportunity in memory and return it.
    Persistence is left to the caller.
    """

    def accept(self, opportunity: TradeOpportunity, trade_id: int) -> TradeOpportunity:
        """Transition ACTIVE → TAKEN and record the linked trade id.

        Parameters
        ----------
        opportunity: The opportunity to accept.
        trade_id:    The id of the Trade journal record created for this opportunity.

        Raises
        ------
        InvalidTransitionError if the opportunity is not currently ACTIVE.
        ValueError if trade_id is not a positive integer.
        """
        if opportunity.status != OpportunityStatus.ACTIVE:
            raise InvalidTransitionError(opportunity.status, OpportunityStatus.TAKEN)
        if trade_id <= 0:
            raise ValueError(f"trade_id must be a positive integer, got {trade_id!r}.")

        opportunity.status = OpportunityStatus.TAKEN
        opportunity.trade_id = trade_id
        opportunity.taken_at = datetime.now(tz=UTC)
        return opportunity

    def reject(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Transition ACTIVE → REJECTED.

        Raises
        ------
        InvalidTransitionError if the opportunity is not currently ACTIVE.
        """
        if opportunity.status != OpportunityStatus.ACTIVE:
            raise InvalidTransitionError(opportunity.status, OpportunityStatus.REJECTED)
        opportunity.status = OpportunityStatus.REJECTED
        return opportunity

    def invalidate(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Transition ACTIVE → INVALIDATED.

        Raised when the strategy detects the setup has failed (e.g. SL broken).

        Raises
        ------
        InvalidTransitionError if the opportunity is not currently ACTIVE.
        """
        if opportunity.status != OpportunityStatus.ACTIVE:
            raise InvalidTransitionError(opportunity.status, OpportunityStatus.INVALIDATED)
        opportunity.status = OpportunityStatus.INVALIDATED
        opportunity.invalidated_at = datetime.now(tz=UTC)
        return opportunity

    def expire(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Transition ACTIVE → EXPIRED.

        Called when the opportunity TTL is exceeded.

        Raises
        ------
        InvalidTransitionError if the opportunity is not currently ACTIVE.
        """
        if opportunity.status != OpportunityStatus.ACTIVE:
            raise InvalidTransitionError(opportunity.status, OpportunityStatus.EXPIRED)
        opportunity.status = OpportunityStatus.EXPIRED
        return opportunity

    def complete(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """Transition TAKEN → COMPLETED.

        Called when the linked trade is closed.

        Raises
        ------
        InvalidTransitionError if the opportunity is not currently TAKEN.
        """
        if opportunity.status != OpportunityStatus.TAKEN:
            raise InvalidTransitionError(opportunity.status, OpportunityStatus.COMPLETED)
        opportunity.status = OpportunityStatus.COMPLETED
        return opportunity
