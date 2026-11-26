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


class ConversationError(KosmosError):
    """Base exception for conversation management failures."""


class SessionNotFoundError(ConversationError):
    """Raised when a conversation session does not exist."""


class SessionBusyError(ConversationError):
    """Raised when an active turn prevents a session operation."""


class ContextLimitExceededError(ConversationError):
    """Raised when required messages exceed the configured context budget."""


class OrchestrationError(KosmosError):
    """Base exception for core orchestration failures."""


class UnsupportedEffortLevelError(OrchestrationError):
    """Raised when a reserved effort level is requested."""


class ToolCapabilityUnavailableError(OrchestrationError):
    """Raised when selected tools require a provider capability that is unavailable."""
