"""Security extension point for future local authentication and authorization."""


def authentication_enabled() -> bool:
    """Return whether authentication is enabled in this initial local-only release."""

    return False
