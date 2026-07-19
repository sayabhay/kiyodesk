"""FastAPI dependency providers."""

from typing import cast

from fastapi import Request

from app.providers.manager import ProviderManager


def get_provider_manager(request: Request) -> ProviderManager:
    """Retrieve the application-scoped provider manager."""

    return cast(ProviderManager, request.app.state.provider_manager)
