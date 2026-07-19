"""Request and response schemas for the Trade Opportunity API."""

import json
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class OpportunityResponse(BaseModel):
    """A persisted TradeOpportunity returned by the API."""

    id: int
    strategy: str
    strategy_version: str | None
    symbol: str
    timeframe: str | None
    direction: str
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_reward: Decimal
    status: str

    # Lifecycle timestamps
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    taken_at: datetime | None
    invalidated_at: datetime | None

    # Journal link
    trade_id: int | None

    # Domain Engine outputs (placeholders until v0.6 / v0.7)
    confidence: Decimal | None  # null → "Coming in Sprint 3"
    market_regime: str | None  # null → "Coming in Sprint 4"

    # Parsed from trade_setup_json for convenience
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Raw JSON for clients that want the full TradeSetup
    trade_setup_json: str

    @model_validator(mode="before")
    @classmethod
    def _extract_reasons_warnings(cls, data: object) -> object:
        """Parse reasons and warnings out of trade_setup_json if not already set."""
        if not isinstance(data, dict):
            return data
        if data.get("reasons") or data.get("warnings"):
            return data
        raw = data.get("trade_setup_json")
        if raw:
            try:
                parsed = json.loads(raw)
                data["reasons"] = parsed.get("reasons", [])
                data["warnings"] = parsed.get("warnings", [])
            except (json.JSONDecodeError, AttributeError):
                pass
        return data

    model_config = {"from_attributes": True}


class RejectOpportunityRequest(BaseModel):
    """Optional body when rejecting an opportunity."""

    notes: str | None = Field(default=None, max_length=1000)


class AcceptOpportunityRequest(BaseModel):
    """Body for accepting an opportunity (currently empty — trade is auto-created)."""

    pass
