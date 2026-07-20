"""Settings API endpoints.

GET  /api/v1/settings   — return current dashboard settings
PUT  /api/v1/settings   — update or create settings
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.repositories.settings_repository import SettingsRepository
from app.schemas.events import Event
from app.services.event_bus import event_bus
from app.schemas.settings import (
    DashboardSettingsResponse,
    UpdateDashboardSettingsRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=DashboardSettingsResponse)
async def get_settings(session: AsyncSession = Depends(get_session)) -> DashboardSettingsResponse:
    repo = SettingsRepository(session)
    settings = await repo.get()
    if settings is None:
        settings = await repo.create_default()
    return DashboardSettingsResponse.model_validate(settings)


@router.put("", response_model=DashboardSettingsResponse)
async def update_settings(
    payload: UpdateDashboardSettingsRequest,
    session: AsyncSession = Depends(get_session),
) -> DashboardSettingsResponse:
    repo = SettingsRepository(session)
    values = payload.model_dump(exclude_unset=True)
    settings = await repo.upsert(values)
    
    # PR-6: Publish SettingsUpdated event
    await event_bus.publish(Event(
        event_type="SettingsUpdated",
        source="SettingsAPI",
        payload=values
    ))
    
    return DashboardSettingsResponse.model_validate(settings)
