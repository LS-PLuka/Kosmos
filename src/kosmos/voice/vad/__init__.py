"""Independent Voice Activity Detection and speech-segmentation contracts."""

from kosmos.voice.vad.config import VADSettings, load_vad_settings
from kosmos.voice.vad.framing import AudioFramer
from kosmos.voice.vad.models import (
    AudioWindow,
    SegmentationResult,
    SpeechEvent,
    SpeechEventType,
    Utterance,
    UtteranceEndReason,
    VoiceActivityMetrics,
    VoiceActivityResult,
    VoiceActivityState,
)
from kosmos.voice.vad.ports import SpeechSegmenter, VoiceActivityDetector

__all__ = [
    "AudioFramer",
    "AudioWindow",
    "SegmentationResult",
    "SpeechEvent",
    "SpeechEventType",
    "SpeechSegmenter",
    "Utterance",
    "UtteranceEndReason",
    "VADSettings",
    "VoiceActivityDetector",
    "VoiceActivityMetrics",
    "VoiceActivityResult",
    "VoiceActivityState",
    "load_vad_settings",
]
