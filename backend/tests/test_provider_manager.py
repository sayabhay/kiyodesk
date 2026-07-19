"""Unit coverage for the provider abstraction."""

import pytest
from app.providers.manager import ProviderManager


def test_provider_manager_rejects_unknown_provider() -> None:
    """The manager gives an actionable error for a missing provider name."""

    manager = ProviderManager([])

    with pytest.raises(ValueError, match="not registered"):
        manager.get("unknown")
