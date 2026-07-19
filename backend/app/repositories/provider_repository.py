"""Repository for provider configuration state."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider


class ProviderRepository:
    """Encapsulate provider persistence queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self) -> list[Provider]:
        """Return persisted enabled provider rows."""

        result = await self._session.scalars(select(Provider).where(Provider.enabled.is_(True)))
        return list(result)
