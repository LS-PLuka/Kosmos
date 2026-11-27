"""Backend-independent wake-word models."""

import math
from dataclasses import dataclass
from enum import StrEnum

from kosmos.voice.audio.models import AudioChunk, SampleFormat
from kosmos.voice.exceptions import InvalidWakeWordInputError, InvalidWakeWordResultError

WAKE_WORD_SAMPLE_RATE = 16_000
WAKE_WORD_FRAME_SIZE = 1_280


class WakeWordOperationalState(StrEnum):
    """Operational state of one detector instance."""

    UNLOADED = "unloaded"
    WARMING_UP = "warming_up"
    READY = "ready"
    FAILED = "failed"
    CLOSED = "closed"


class WakeWordActivationState(StrEnum):
    """Deterministic state of one activation policy."""

    ARMED = "armed"
    POSSIBLE_ACTIVATION = "possible_activation"
    COOLDOWN = "cooldown"
    REARM = "rearm"


@dataclass(frozen=True, slots=True)
class WakeWordWindow:
    """One complete 80 ms PCM region on an absolute acoustic timeline."""

    audio: AudioChunk
    start_frame: int

    def __post_init__(self) -> None:
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise InvalidWakeWordInputError("Window start frame must be an integer")
        if self.start_frame < 0:
            raise InvalidWakeWordInputError("Window start frame must not be negative")
        if (
            self.audio.format.sample_rate != WAKE_WORD_SAMPLE_RATE
            or self.audio.format.channels != 1
        ):
            raise InvalidWakeWordInputError("Wake-word windows require mono PCM at 16000 Hz")
        if self.audio.format.sample_format is not SampleFormat.SIGNED_16_LE:
            raise InvalidWakeWordInputError(
                "Wake-word windows require signed 16-bit little-endian PCM"
            )
        if self.audio.frame_count != WAKE_WORD_FRAME_SIZE:
            raise InvalidWakeWordInputError("Wake-word windows must contain exactly 1280 frames")

    @property
    def end_frame(self) -> int:
        return self.start_frame + self.audio.frame_count


@dataclass(frozen=True, slots=True)
class WakeWordResult:
    """One validated classifier score for an ordered audio window."""

    score: float
    start_frame: int
    end_frame: int
    inference_seconds: float
    ready: bool

    def __post_init__(self) -> None:
        for value, name in ((self.score, "Score"), (self.inference_seconds, "Inference duration")):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InvalidWakeWordResultError(f"{name} must be numeric")
            if not math.isfinite(value):
                raise InvalidWakeWordResultError(f"{name} must be finite")
        if not 0 <= self.score <= 1:
            raise InvalidWakeWordResultError("Wake-word score must be from zero to one")
        if self.inference_seconds < 0:
            raise InvalidWakeWordResultError("Inference duration must not be negative")
        if not isinstance(self.ready, bool):
            raise InvalidWakeWordResultError("Warm-up readiness must be boolean")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.start_frame, self.end_frame)
        ):
            raise InvalidWakeWordResultError("Result positions must be non-negative integers")
        if self.end_frame - self.start_frame != WAKE_WORD_FRAME_SIZE:
            raise InvalidWakeWordResultError("Result must describe one complete wake-word window")


@dataclass(frozen=True, slots=True)
class WakeWordDetection:
    """A confirmed activation at the end of a scored acoustic window."""

    phrase: str
    model_identifier: str
    score: float
    detection_frame: int

    def __post_init__(self) -> None:
        if not self.phrase.strip() or not self.model_identifier.strip():
            raise InvalidWakeWordResultError("Detection identity must not be empty")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise InvalidWakeWordResultError("Detection score must be numeric")
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise InvalidWakeWordResultError("Detection score must be finite and from zero to one")
        if (
            isinstance(self.detection_frame, bool)
            or not isinstance(self.detection_frame, int)
            or self.detection_frame < 0
        ):
            raise InvalidWakeWordResultError("Detection frame must be a non-negative integer")

    @property
    def detection_timestamp_seconds(self) -> float:
        return self.detection_frame / WAKE_WORD_SAMPLE_RATE


@dataclass(frozen=True, slots=True)
class WakeWordMetrics:
    """Finite measurements observed by one detector instance."""

    backend: str
    model_identifier: str
    audio_frames_processed: int
    inference_count: int
    warmup_frames: int
    model_loading_seconds: float
    inference_seconds: float

    def __post_init__(self) -> None:
        if not self.backend.strip() or not self.model_identifier.strip():
            raise InvalidWakeWordResultError("Wake-word metric identity must not be empty")
        for value, name in (
            (self.audio_frames_processed, "Processed audio frames"),
            (self.inference_count, "Inference count"),
            (self.warmup_frames, "Warm-up frames"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidWakeWordResultError(f"{name} must be a non-negative integer")
        for value, name in (
            (self.model_loading_seconds, "Model loading duration"),
            (self.inference_seconds, "Inference duration"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise InvalidWakeWordResultError(f"{name} must be finite and non-negative")

    @property
    def real_time_factor(self) -> float:
        if self.audio_frames_processed == 0:
            return 0.0
        return self.inference_seconds / (self.audio_frames_processed / WAKE_WORD_SAMPLE_RATE)
