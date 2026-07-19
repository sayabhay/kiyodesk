"""System health endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_provider_manager
from app.database.session import get_session
from app.providers.manager import ProviderManager
from app.schemas.system import HealthResponse
from app.services.system_service import SystemService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(
    session: AsyncSession = Depends(get_session),
    providers: ProviderManager = Depends(get_provider_manager),
) -> HealthResponse:
    """Report application, database, and provider registration health."""

    from app.core.config import get_settings

    return await SystemService(session, providers, get_settings().app_version).health()
