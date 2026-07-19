"""Typed provider failures that API routes can safely translate."""


class ProviderError(Exception):
    """Base exception for a failed external provider operation."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider has not been configured locally."""


class ProviderRateLimitError(ProviderError):
    """Raised before a request would exceed the configured local quota."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an invalid or unsuccessful response."""
