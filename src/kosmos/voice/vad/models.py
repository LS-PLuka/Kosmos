"""Backend-independent models for voice activity and speech segmentation."""

import math
from dataclasses import dataclass
from enum import StrEnum

from kosmos.voice.audio.models import AudioChunk, SampleFormat
from kosmos.voice.exceptions import InvalidSpeechSegmentError, InvalidVoiceActivityResultError

VAD_SAMPLE_RATE = 16_000
VAD_FRAME_SIZE = 512
VAD_CONTEXT_SIZE = 64


class VoiceActivityState(StrEnum):
    """Operational state of one detector instance."""

    UNLOADED = "unloaded"
    READY = "ready"
    FAILED = "failed"
    CLOSED = "closed"


class SpeechEventType(StrEnum):
    """Events returned directly by one segmenter operation."""

    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    UTTERANCE_COMPLETED = "utterance_completed"
    UTTERANCE_DISCARDED = "utterance_discarded"


class UtteranceEndReason(StrEnum):
    """Explicit reason why a bounded utterance ended."""

    SILENCE = "silence"
    MAX_DURATION = "max_duration"
    STREAM_ENDED = "stream_ended"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AudioWindow:
    """A real PCM region and its fixed inference-window contract."""

    audio: AudioChunk
    start_frame: int
    inference_frame_size: int = VAD_FRAME_SIZE

    def __post_init__(self) -> None:
        if self.inference_frame_size != VAD_FRAME_SIZE:
            raise InvalidSpeechSegmentError("Silero inference window must contain 512 frames")
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise InvalidSpeechSegmentError("Window start frame must be an integer")
        if self.start_frame < 0:
            raise InvalidSpeechSegmentError("Window start frame must not be negative")
        if self.audio.format.sample_rate != VAD_SAMPLE_RATE or self.audio.format.channels != 1:
            raise InvalidSpeechSegmentError("VAD windows require mono PCM at 16000 Hz")
        if self.audio.format.sample_format is not SampleFormat.SIGNED_16_LE:
            raise InvalidSpeechSegmentError("VAD windows require signed 16-bit little-endian PCM")
        if not 0 < self.audio.frame_count <= self.inference_frame_size:
            raise InvalidSpeechSegmentError("VAD window must contain 1 to 512 real frames")

    @property
    def end_frame(self) -> int:
        return self.start_frame + self.audio.frame_count

    @property
    def inference_pcm(self) -> bytes:
        """Return zero-padded PCM for inference without changing real audio duration."""

        missing = self.inference_frame_size - self.audio.frame_count
        return self.audio.data + (b"\x00\x00" * missing)


@dataclass(frozen=True, slots=True)
class VoiceActivityResult:
    """Validated probability for one ordered audio window."""

    probability: float
    start_frame: int
    audio_frame_count: int
    inference_seconds: float

    def __post_init__(self) -> None:
        numeric = (self.probability, self.inference_seconds)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numeric):
            raise InvalidVoiceActivityResultError("VAD result values must be numeric")
        if not all(math.isfinite(value) for value in numeric):
            raise InvalidVoiceActivityResultError("VAD result values must be finite")
        if not 0 <= self.probability <= 1:
            raise InvalidVoiceActivityResultError("Speech probability must be from zero to one")
        if self.inference_seconds < 0:
            raise InvalidVoiceActivityResultError("Inference duration must not be negative")
        for value, name in (
            (self.start_frame, "Result start frame"),
            (self.audio_frame_count, "Result frame count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidVoiceActivityResultError(f"{name} must be a non-negative integer")
        if self.audio_frame_count == 0 or self.audio_frame_count > VAD_FRAME_SIZE:
            raise InvalidVoiceActivityResultError("Result frame count must be from 1 to 512")


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    """One deterministic segmentation transition on the acoustic timeline."""

    type: SpeechEventType
    frame: int
    utterance_id: int | None = None
    end_reason: UtteranceEndReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, SpeechEventType):
            raise InvalidSpeechSegmentError("Speech event type is invalid")
        if isinstance(self.frame, bool) or not isinstance(self.frame, int) or self.frame < 0:
            raise InvalidSpeechSegmentError("Speech event frame must be a non-negative integer")
        if self.utterance_id is not None and (
            isinstance(self.utterance_id, bool)
            or not isinstance(self.utterance_id, int)
            or self.utterance_id <= 0
        ):
            raise InvalidSpeechSegmentError("Utterance identifier must be a positive integer")
        if self.end_reason is not None and not isinstance(self.end_reason, UtteranceEndReason):
            raise InvalidSpeechSegmentError("Utterance end reason is invalid")
        if self.type is SpeechEventType.SPEECH_STARTED:
            if self.utterance_id is None or self.end_reason is not None:
                raise InvalidSpeechSegmentError("Speech-started event metadata is inconsistent")
        elif self.type is SpeechEventType.UTTERANCE_DISCARDED:
            if self.end_reason is None:
                raise InvalidSpeechSegmentError("Discarded event requires an end reason")
        elif self.utterance_id is None or self.end_reason is None:
            raise InvalidSpeechSegmentError("Completed speech event metadata is incomplete")

    @property
    def timestamp_seconds(self) -> float:
        return self.frame / VAD_SAMPLE_RATE


@dataclass(frozen=True, slots=True)
class Utterance:
    """A bounded PCM region ready for a future explicit STT request."""

    identifier: int
    audio: AudioChunk
    start_frame: int
    end_frame: int
    speech_start_frame: int
    speech_end_frame: int
    end_reason: UtteranceEndReason

    def __post_init__(self) -> None:
        if (
            isinstance(self.identifier, bool)
            or not isinstance(self.identifier, int)
            or self.identifier <= 0
        ):
            raise InvalidSpeechSegmentError("Utterance identifier must be positive")
        positions = (
            self.start_frame,
            self.speech_start_frame,
            self.speech_end_frame,
            self.end_frame,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in positions):
            raise InvalidSpeechSegmentError("Utterance positions must be integers")
        if not 0 <= self.start_frame <= self.speech_start_frame <= self.speech_end_frame:
            raise InvalidSpeechSegmentError("Utterance speech positions are inconsistent")
        if self.speech_end_frame > self.end_frame:
            raise InvalidSpeechSegmentError("Utterance end positions are inconsistent")
        if (
            self.audio.frame_count == 0
            or self.audio.frame_count != self.end_frame - self.start_frame
        ):
            raise InvalidSpeechSegmentError("Utterance audio does not match its timeline")
        if self.audio.format.sample_rate != VAD_SAMPLE_RATE or self.audio.format.channels != 1:
            raise InvalidSpeechSegmentError("Utterance audio format is incompatible")
        if self.audio.format.sample_format is not SampleFormat.SIGNED_16_LE:
            raise InvalidSpeechSegmentError("Utterance PCM encoding is incompatible")
        if not isinstance(self.end_reason, UtteranceEndReason):
            raise InvalidSpeechSegmentError("Utterance end reason is invalid")

    @property
    def duration_seconds(self) -> float:
        return self.audio.duration_seconds


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """Events and utterances produced while consuming one input region."""

    events: tuple[SpeechEvent, ...] = ()
    utterances: tuple[Utterance, ...] = ()


@dataclass(frozen=True, slots=True)
class VoiceActivityMetrics:
    """Finite observed measurements for one detector instance."""

    backend: str
    model_revision: str
    device: str
    sample_rate: int
    frame_size: int
    audio_frames_processed: int
    inference_count: int
    model_loading_seconds: float
    inference_seconds: float

    def __post_init__(self) -> None:
        if not self.backend.strip() or not self.model_revision.strip() or self.device != "cpu":
            raise InvalidVoiceActivityResultError("VAD metric identity is invalid")
        for value, name in (
            (self.sample_rate, "Metric sample rate"),
            (self.frame_size, "Metric frame size"),
            (self.audio_frames_processed, "Processed audio frames"),
            (self.inference_count, "Inference count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidVoiceActivityResultError(f"{name} must be non-negative")
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
                raise InvalidVoiceActivityResultError(f"{name} must be finite and non-negative")

    @property
    def processed_audio_seconds(self) -> float:
        return self.audio_frames_processed / self.sample_rate

    @property
    def inference_real_time_factor(self) -> float:
        duration = self.processed_audio_seconds
        return self.inference_seconds / duration if duration else 0.0
