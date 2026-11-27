"""Backend-independent speech-to-text contracts."""

from kosmos.voice.stt.models import (
    SpeechRecognitionMetrics,
    SpeechRecognitionRequest,
    SpeechRecognitionResult,
    SpeechRecognitionStatus,
    TranscriptionSegment,
)
from kosmos.voice.stt.ports import SpeechRecognizer

__all__ = [
    "SpeechRecognitionMetrics",
    "SpeechRecognitionRequest",
    "SpeechRecognitionResult",
    "SpeechRecognitionStatus",
    "SpeechRecognizer",
    "TranscriptionSegment",
]
