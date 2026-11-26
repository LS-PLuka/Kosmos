"""Fundamental Kosmos exceptions."""


class KosmosError(Exception):
    """Base exception for expected Kosmos failures."""


class ConfigurationError(KosmosError):
    """Raised when application configuration is invalid."""


class InferenceError(KosmosError):
    """Raised when an inference operation fails."""


class ProviderUnavailableError(InferenceError):
    """Raised when a provider service cannot be reached."""


class ProviderTimeoutError(InferenceError):
    """Raised when a provider transport operation times out."""


class ProviderHTTPError(InferenceError):
    """Raised when a provider returns an unsuccessful HTTP status."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidProviderResponseError(InferenceError):
    """Raised when a provider response violates its documented schema."""
