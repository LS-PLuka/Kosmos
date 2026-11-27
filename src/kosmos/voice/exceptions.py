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


class SpeechSynthesisError(VoiceError):
    """Base exception for expected text-to-speech failures."""


class TTSBackendUnavailableError(SpeechSynthesisError):
    """Raised when the configured local synthesis backend cannot be executed."""


class VoiceModelUnavailableError(SpeechSynthesisError):
    """Raised when configured voice files are missing or unavailable."""


class InvalidVoiceConfigurationError(SpeechSynthesisError):
    """Raised when synthesis or voice-model configuration is invalid."""


class InvalidSynthesisRequestError(SpeechSynthesisError):
    """Raised when text or request settings violate synthesis limits."""


class SynthesisTimeoutError(SpeechSynthesisError):
    """Raised when a synthesis process exceeds its configured deadline."""


class InvalidSynthesizedAudioError(SpeechSynthesisError):
    """Raised when a backend returns empty, partial, or excessive PCM."""


class SpeechRecognitionError(VoiceError):
    """Base exception for expected speech-to-text failures."""


class STTBackendUnavailableError(SpeechRecognitionError):
    """Raised when the optional recognition backend cannot be loaded."""


class SpeechRecognitionDisabledError(SpeechRecognitionError):
    """Raised when recognition has not been explicitly enabled."""


class SpeechModelUnavailableError(SpeechRecognitionError):
    """Raised when configured local model files are unavailable."""


class InvalidSpeechModelError(SpeechRecognitionError):
    """Raised when local model files or metadata are invalid."""


class InvalidRecognitionRequestError(SpeechRecognitionError):
    """Raised when audio or recognition settings violate limits."""


class SpeechRecognitionBusyError(SpeechRecognitionError):
    """Raised when a recognizer already owns native inference work."""


class InvalidTranscriptionResultError(SpeechRecognitionError):
    """Raised when a backend returns inconsistent transcription data."""
