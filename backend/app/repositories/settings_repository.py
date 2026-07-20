"""Repository for DashboardSettings persistence operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_settings import DashboardSettings


class SettingsRepository:
    """CRUD wrapper for the single DashboardSettings row."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> DashboardSettings | None:
        """Return the active settings row, or None."""
        query = select(DashboardSettings).limit(1)
        result = await self._session.scalar(query)
        return result

    async def create_default(self, defaults: dict | None = None) -> DashboardSettings:
        """Create and persist a default settings row."""
        defaults = defaults or {}
        settings = DashboardSettings(**defaults)
        self._session.add(settings)
        await self._session.commit()
        await self._session.refresh(settings)
        return settings

    async def upsert(self, values: dict) -> DashboardSettings:
        """Update the existing settings row or create one if missing."""
        settings = await self.get()
        if settings is None:
            settings = DashboardSettings(**values)
            self._session.add(settings)
        else:
            for k, v in values.items():
                setattr(settings, k, v)

        await self._session.commit()
        await self._session.refresh(settings)
        return settings
