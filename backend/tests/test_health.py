"""Integration coverage for the initial public health API."""

from app.core.config import get_settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_reports_database_and_provider_registration() -> None:
    """The startup path creates SQLite tables and serves the expected health contract."""

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
        docs_response = client.get("/docs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "0.1.0"
    assert body["database"] == "connected"

    # Provider list reflects the active MARKET_PROVIDERS configuration —
    # tested against the real settings so the test stays valid as .env evolves.
    expected_providers = get_settings().active_providers
    assert body["providers"] == expected_providers

    assert docs_response.status_code == 200
