"""Tests for the dashboard settings API endpoints."""

import pytest
from app.database.base import Base
from app.database.session import get_session
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
def client() -> TestClient:  # type: ignore[misc]
    """TestClient backed by an isolated in-memory database."""
    from collections.abc import AsyncIterator

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


class TestSettingsAPI:
    def test_get_settings_returns_defaults(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["symbols"] is None
        assert data["risk_percent"] is None

    def test_update_settings_persists_values(self, client: TestClient) -> None:
        payload = {
            "symbols": "BTC",
            "timeframes": "15m",
            "risk_percent": "0.5",
            "max_concurrent_trades": 2,
            "execution_mode": "paper",
        }

        response = client.put("/api/v1/settings", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == "BTC"
        assert data["timeframes"] == "15m"
        assert data["risk_percent"] == "0.500000"
        assert data["max_concurrent_trades"] == 2
        assert data["execution_mode"] == "paper"

    def test_get_settings_returns_updated_row(self, client: TestClient) -> None:
        client.put("/api/v1/settings", json={"risk_percent": "0.75"})
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["risk_percent"] == "0.750000"
