"""System health business logic."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.manager import ProviderManager
from app.schemas.system import HealthResponse


class SystemService:
    """Build system status responses without embedding logic in routes."""

    def __init__(self, session: AsyncSession, providers: ProviderManager, version: str) -> None:
        self._session = session
        self._providers = providers
        self._version = version

    async def health(self) -> HealthResponse:
        """Verify database connectivity and return registered provider names."""

        try:
            await self._session.execute(text("SELECT 1"))
            database = "connected"
        except Exception:
            database = "unavailable"

        return HealthResponse(
            status="healthy" if database == "connected" else "degraded",
            version=self._version,
            database=database,
            providers=self._providers.names(),
        )
