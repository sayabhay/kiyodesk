"""Provider status endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_provider_manager
from app.providers.manager import ProviderManager

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
async def list_providers(
    providers: ProviderManager = Depends(get_provider_manager),
) -> dict[str, list[str]]:
    """List all registered runtime providers."""

    return {"providers": providers.names()}


@router.get("/status")
async def provider_statuses(
    providers: ProviderManager = Depends(get_provider_manager),
) -> dict[str, dict[str, bool]]:
    """Report health state for every registered provider."""

    return {"providers": await providers.statuses()}
