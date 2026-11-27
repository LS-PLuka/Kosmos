"""Expected Voice Foundation failures."""

from kosmos.core.exceptions import KosmosError


class VoiceError(KosmosError):
    """Base exception for expected voice failures."""


class AudioBackendUnavailableError(VoiceError):
    """Raised when the optional audio backend cannot be loaded."""


class AudioDeviceNotFoundError(VoiceError):
    """Raised when a requested or default device is unavailable."""


class AudioConfigurationError(VoiceError):
    """Raised when an audio format or voice setting is invalid."""


class AudioCaptureError(VoiceError):
    """Raised when bounded audio capture cannot complete safely."""


class AudioPlaybackError(VoiceError):
    """Raised when PCM playback cannot complete safely."""


class AudioBufferOverflowError(VoiceError):
    """Raised when appending PCM would exceed an explicit memory limit."""
