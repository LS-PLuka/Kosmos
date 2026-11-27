"""Public Text-to-Speech contracts, models, and configuration."""

from kosmos.voice.tts.config import TTSSettings, VoiceMetadata, load_tts_settings
from kosmos.voice.tts.models import (
    SpeechSynthesisMetrics,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    SpeechSynthesisSettings,
    SpeechVoice,
)
from kosmos.voice.tts.ports import SpeechSynthesizer
from kosmos.voice.tts.text import prepare_text, segment_text

__all__ = [
    "SpeechSynthesisMetrics",
    "SpeechSynthesisRequest",
    "SpeechSynthesisResult",
    "SpeechSynthesisSettings",
    "SpeechSynthesizer",
    "SpeechVoice",
    "TTSSettings",
    "VoiceMetadata",
    "load_tts_settings",
    "prepare_text",
    "segment_text",
]
