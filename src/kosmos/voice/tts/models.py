"""Immutable, backend-independent text-to-speech models."""

import math
from dataclasses import dataclass, field

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import (
    InvalidSynthesisRequestError,
    InvalidSynthesizedAudioError,
)

MAX_TEXT_CHARACTERS = 8_000
MAX_SEGMENT_CHARACTERS = 1_000
MAX_SYNTHESIZED_AUDIO_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SpeechVoice:
    """Configured local voice metadata."""

    identifier: str
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.identifier.strip() or len(self.identifier) > 128:
            raise InvalidSynthesisRequestError("Voice identifier must contain 1 to 128 characters")
        if self.language is not None and (not self.language.strip() or len(self.language) > 35):
            raise InvalidSynthesisRequestError("Voice language must contain 1 to 35 characters")


@dataclass(frozen=True, slots=True)
class SpeechSynthesisSettings:
    """Portable synthesis controls supported by the current adapter."""

    length_scale: float = 1.0
    volume: float = 1.0

    def __post_init__(self) -> None:
        _bounded_number(self.length_scale, "Length scale", minimum=0.1, maximum=10.0)
        _bounded_number(self.volume, "Volume", minimum=0.0, maximum=10.0)


@dataclass(frozen=True, slots=True)
class SpeechSynthesisRequest:
    """One bounded text request for a configured voice."""

    text: str
    voice: SpeechVoice
    settings: SpeechSynthesisSettings = field(default_factory=SpeechSynthesisSettings)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise InvalidSynthesisRequestError("Synthesis text must not be empty")
        if len(self.text) > MAX_TEXT_CHARACTERS:
            raise InvalidSynthesisRequestError(
                f"Synthesis text exceeds the {MAX_TEXT_CHARACTERS}-character request limit"
            )
        if not isinstance(self.voice, SpeechVoice):
            raise InvalidSynthesisRequestError("Synthesis request requires a valid voice")
        if not isinstance(self.settings, SpeechSynthesisSettings):
            raise InvalidSynthesisRequestError("Synthesis request requires valid settings")


@dataclass(frozen=True, slots=True)
class SpeechSynthesisMetrics:
    """Measured process-level synthesis metadata without text or raw PCM."""

    backend: str
    voice_identifier: str
    text_characters: int
    process_duration_seconds: float
    audio_duration_seconds: float
    sample_rate: int
    audio_frames: int
    audio_bytes: int

    def __post_init__(self) -> None:
        if not self.backend.strip():
            raise InvalidSynthesizedAudioError("Synthesis backend identifier must not be empty")
        for value, name in (
            (self.text_characters, "Text characters"),
            (self.sample_rate, "Sample rate"),
            (self.audio_frames, "Audio frames"),
            (self.audio_bytes, "Audio bytes"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise InvalidSynthesizedAudioError(f"{name} must be a positive integer")
        for value, name in (
            (self.process_duration_seconds, "Process duration"),
            (self.audio_duration_seconds, "Audio duration"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise InvalidSynthesizedAudioError(f"{name} must be finite and positive")

    @property
    def real_time_factor(self) -> float:
        """Return process duration divided by generated audio duration."""

        return self.process_duration_seconds / self.audio_duration_seconds


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    """Validated synthesized PCM and its measured metadata."""

    audio: AudioChunk
    metrics: SpeechSynthesisMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.audio, AudioChunk) or not self.audio.data:
            raise InvalidSynthesizedAudioError("Synthesized audio must contain PCM frames")
        if len(self.audio.data) > MAX_SYNTHESIZED_AUDIO_BYTES:
            raise InvalidSynthesizedAudioError("Synthesized audio exceeds the 64 MiB limit")
        if self.metrics.audio_frames != self.audio.frame_count:
            raise InvalidSynthesizedAudioError("Synthesis metrics do not match PCM frame count")
        if self.metrics.audio_bytes != len(self.audio.data):
            raise InvalidSynthesizedAudioError("Synthesis metrics do not match PCM byte count")


def _bounded_number(value: object, name: str, *, minimum: float, maximum: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise InvalidSynthesisRequestError(
            f"{name} must be finite and from {minimum:g} to {maximum:g}"
        )
