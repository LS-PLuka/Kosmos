"""Fundamental Kosmos exceptions."""


class KosmosError(Exception):
    """Base exception for expected Kosmos failures."""


class ConfigurationError(KosmosError):
    """Raised when application configuration is invalid."""


class InferenceError(KosmosError):
    """Raised when an inference operation fails."""
