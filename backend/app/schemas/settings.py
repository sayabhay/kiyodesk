"""Request and response schemas for dashboard settings."""

from decimal import Decimal

from pydantic import BaseModel


class DashboardSettingsResponse(BaseModel):
    """A persisted dashboard settings row."""

    id: int
    symbols: str | None = None
    timeframes: str | None = None
    htf_mapping_json: str | None = None
    risk_percent: Decimal | None = None
    fixed_risk: Decimal | None = None
    stop_loss_mode: str | None = None
    swing_buffer: Decimal | None = None
    reward_ratio: Decimal | None = None
    max_concurrent_trades: int | None = None
    max_daily_loss: Decimal | None = None
    max_weekly_loss: Decimal | None = None
    execution_mode: str | None = None
    account_balance: Decimal | None = None
    metadata_json: str | None = None

    model_config = {"from_attributes": True}


class UpdateDashboardSettingsRequest(BaseModel):
    """Upsert payload for dashboard settings."""

    symbols: str | None = None
    timeframes: str | None = None
    htf_mapping_json: str | None = None
    risk_percent: Decimal | None = None
    fixed_risk: Decimal | None = None
    stop_loss_mode: str | None = None
    swing_buffer: Decimal | None = None
    reward_ratio: Decimal | None = None
    max_concurrent_trades: int | None = None
    max_daily_loss: Decimal | None = None
    max_weekly_loss: Decimal | None = None
    execution_mode: str | None = None
    account_balance: Decimal | None = None
    metadata_json: str | None = None
