"""Settings API endpoints.

GET  /api/v1/settings   — return current dashboard settings
PUT  /api/v1/settings   — update or create settings
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.repositories.settings_repository import SettingsRepository

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=dict)
async def get_settings(session: AsyncSession = Depends(get_session)) -> dict:
    repo = SettingsRepository(session)
    settings = await repo.get()
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not configured.")
    return {k: getattr(settings, k) for k in settings.__dict__ if not k.startswith("_")}


@router.put("", response_model=dict)
async def update_settings(payload: dict, session: AsyncSession = Depends(get_session)) -> dict:
    repo = SettingsRepository(session)
    settings = await repo.upsert(payload)
    return {k: getattr(settings, k) for k in settings.__dict__ if not k.startswith("_")}
