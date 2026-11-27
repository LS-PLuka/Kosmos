"""Immutable, backend-independent speech recognition models."""

import math
from dataclasses import dataclass
from enum import StrEnum

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import (
    InvalidRecognitionRequestError,
    InvalidTranscriptionResultError,
)

MAX_AUDIO_SECONDS = 30.0
MAX_TRANSCRIPT_CHARACTERS = 16_000
MAX_SEGMENTS = 1_000


class SpeechRecognitionStatus(StrEnum):
    """Normal outcomes produced by one complete recognition operation."""

    TRANSCRIBED = "transcribed"
    NO_TRANSCRIPTION = "no_transcription"


@dataclass(frozen=True, slots=True)
class SpeechRecognitionRequest:
    """One bounded in-memory PCM request."""

    audio: AudioChunk

    def __post_init__(self) -> None:
        if not isinstance(self.audio, AudioChunk):
            raise InvalidRecognitionRequestError("Recognition requires a valid AudioChunk")
        if not self.audio.data:
            raise InvalidRecognitionRequestError("Recognition audio must contain PCM frames")


@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    """Validated temporal transcription returned by a backend."""

    start_seconds: float
    end_seconds: float
    text: str
    average_log_probability: float
    no_speech_probability: float

    def __post_init__(self) -> None:
        _finite(self.start_seconds, "Segment start", minimum=0.0)
        _finite(self.end_seconds, "Segment end", minimum=0.0)
        if self.end_seconds < self.start_seconds:
            raise InvalidTranscriptionResultError("Segment end must not precede its start")
        if not isinstance(self.text, str):
            raise InvalidTranscriptionResultError("Segment text must be Unicode text")
        _finite(self.average_log_probability, "Average log probability")
        _finite(self.no_speech_probability, "No-speech probability", minimum=0.0, maximum=1.0)


@dataclass(frozen=True, slots=True)
class SpeechRecognitionMetrics:
    """Measured recognition metadata containing no transcript or PCM."""

    backend: str
    model_identifier: str
    device: str
    compute_type: str
    configured_language: str
    audio_duration_seconds: float
    audio_frames: int
    audio_bytes: int
    model_loading_seconds: float
    recognition_seconds: float
    total_seconds: float
    segment_count: int
    transcript_characters: int
    model_reused: bool

    def __post_init__(self) -> None:
        for value, name in (
            (self.backend, "Backend"),
            (self.model_identifier, "Model identifier"),
            (self.device, "Device"),
            (self.compute_type, "Compute type"),
            (self.configured_language, "Configured language"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise InvalidTranscriptionResultError(f"{name} must not be empty")
        for value, name in (
            (self.audio_frames, "Audio frames"),
            (self.audio_bytes, "Audio bytes"),
            (self.segment_count, "Segment count"),
            (self.transcript_characters, "Transcript characters"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidTranscriptionResultError(f"{name} must be a non-negative integer")
        for value, name in (
            (self.audio_duration_seconds, "Audio duration"),
            (self.model_loading_seconds, "Model loading duration"),
            (self.recognition_seconds, "Recognition duration"),
            (self.total_seconds, "Total duration"),
        ):
            _finite(value, name, minimum=0.0)
        if self.audio_duration_seconds <= 0:
            raise InvalidTranscriptionResultError("Audio duration must be positive")
        if not isinstance(self.model_reused, bool):
            raise InvalidTranscriptionResultError("Model reused must be a boolean")

    @property
    def real_time_factor(self) -> float:
        return self.recognition_seconds / self.audio_duration_seconds


@dataclass(frozen=True, slots=True)
class SpeechRecognitionResult:
    """Complete immutable recognition outcome."""

    status: SpeechRecognitionStatus
    text: str
    language: str
    segments: tuple[TranscriptionSegment, ...]
    metrics: SpeechRecognitionMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.status, SpeechRecognitionStatus):
            raise InvalidTranscriptionResultError("Recognition status is invalid")
        if not isinstance(self.text, str) or len(self.text) > MAX_TRANSCRIPT_CHARACTERS:
            raise InvalidTranscriptionResultError("Transcript text is invalid or excessive")
        if not isinstance(self.language, str) or not self.language.strip():
            raise InvalidTranscriptionResultError("Recognition language must not be empty")
        if not isinstance(self.segments, tuple) or len(self.segments) > MAX_SEGMENTS:
            raise InvalidTranscriptionResultError("Transcription segments are invalid or excessive")
        if any(not isinstance(segment, TranscriptionSegment) for segment in self.segments):
            raise InvalidTranscriptionResultError("Transcription contains an invalid segment")
        adjacent = zip(self.segments, self.segments[1:], strict=False)
        if any(left.end_seconds > right.start_seconds for left, right in adjacent):
            raise InvalidTranscriptionResultError("Transcription segments must be ordered")
        has_text = bool(self.text.strip())
        if self.status is SpeechRecognitionStatus.TRANSCRIBED and (
            not has_text or not self.segments
        ):
            raise InvalidTranscriptionResultError("A transcribed result requires text and segments")
        if self.status is SpeechRecognitionStatus.NO_TRANSCRIPTION and (has_text or self.segments):
            raise InvalidTranscriptionResultError(
                "No-transcription result must not contain content"
            )
        if self.metrics.segment_count != len(self.segments):
            raise InvalidTranscriptionResultError("Metrics do not match the segment count")
        if self.metrics.transcript_characters != len(self.text):
            raise InvalidTranscriptionResultError("Metrics do not match transcript length")


def _finite(
    value: object,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidTranscriptionResultError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise InvalidTranscriptionResultError(f"{name} must be at least {minimum:g}")
    if maximum is not None and value > maximum:
        raise InvalidTranscriptionResultError(f"{name} must be at most {maximum:g}")
