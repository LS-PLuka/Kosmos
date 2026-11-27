"""Immutable, backend-independent PCM audio models."""

from dataclasses import dataclass
from enum import StrEnum

from kosmos.voice.exceptions import AudioConfigurationError

MIN_SAMPLE_RATE = 8_000
MAX_SAMPLE_RATE = 384_000
MAX_CHANNELS = 32
MAX_CHUNK_BYTES = 64 * 1024 * 1024


class SampleFormat(StrEnum):
    """PCM sample encodings supported by the Voice Foundation."""

    SIGNED_16_LE = "pcm_s16le"

    @property
    def sample_width(self) -> int:
        """Return the number of bytes occupied by one channel sample."""

        return 2


class AudioDeviceDirection(StrEnum):
    """Audio directions supported by a discovered device."""

    INPUT = "input"
    OUTPUT = "output"
    DUPLEX = "duplex"


@dataclass(frozen=True, slots=True)
class AudioFormat:
    """PCM framing information; one frame contains one sample per channel."""

    sample_rate: int
    channels: int
    sample_format: SampleFormat = SampleFormat.SIGNED_16_LE

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_rate, bool)
            or not isinstance(self.sample_rate, int)
            or not MIN_SAMPLE_RATE <= self.sample_rate <= MAX_SAMPLE_RATE
        ):
            raise AudioConfigurationError(
                f"Sample rate must be an integer from {MIN_SAMPLE_RATE} to {MAX_SAMPLE_RATE} Hz"
            )
        if (
            isinstance(self.channels, bool)
            or not isinstance(self.channels, int)
            or not 1 <= self.channels <= MAX_CHANNELS
        ):
            raise AudioConfigurationError(
                f"Channel count must be an integer from 1 to {MAX_CHANNELS}"
            )
        if not isinstance(self.sample_format, SampleFormat):
            raise AudioConfigurationError("Sample format is not supported")

    @property
    def bytes_per_frame(self) -> int:
        """Return bytes occupied by all channel samples at one instant."""

        return self.channels * self.sample_format.sample_width

    def frames_for_duration(self, duration_seconds: float) -> int:
        """Convert a positive duration to a whole number of frames."""

        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or duration_seconds <= 0
        ):
            raise AudioConfigurationError("Duration must be greater than zero")

        frame_count = round(self.sample_rate * duration_seconds)
        if frame_count == 0:
            raise AudioConfigurationError("Duration must contain at least one PCM frame")

        return frame_count


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """A bounded sequence of complete interleaved PCM frames."""

    data: bytes
    format: AudioFormat

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes):
            raise AudioConfigurationError("PCM payload must be bytes")
        if not isinstance(self.format, AudioFormat):
            raise AudioConfigurationError("PCM payload must include a valid audio format")
        if len(self.data) > MAX_CHUNK_BYTES:
            raise AudioConfigurationError("PCM payload exceeds the 64 MiB chunk limit")
        if len(self.data) % self.format.bytes_per_frame:
            raise AudioConfigurationError("PCM payload must contain complete frames")

    @property
    def frame_count(self) -> int:
        """Return complete PCM frames in the payload."""

        return len(self.data) // self.format.bytes_per_frame

    @property
    def duration_seconds(self) -> float:
        """Return duration derived from frames and sample rate."""

        return self.frame_count / self.format.sample_rate


@dataclass(frozen=True, slots=True)
class AudioDevice:
    """One process-local PortAudio device index and its relevant capabilities."""

    index: int
    name: str
    host_api: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    is_default_input: bool = False
    is_default_output: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise AudioConfigurationError("Device index must be a non-negative integer")
        if not self.name.strip():
            raise AudioConfigurationError("Device name must not be empty")
        if not self.host_api.strip():
            raise AudioConfigurationError("Host API name must not be empty")
        for count, field_name in (
            (self.max_input_channels, "Maximum input channels"),
            (self.max_output_channels, "Maximum output channels"),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise AudioConfigurationError(f"{field_name} must be a non-negative integer")
        if self.max_input_channels == 0 and self.max_output_channels == 0:
            raise AudioConfigurationError("Device must support input or output")
        if (
            isinstance(self.default_sample_rate, bool)
            or not isinstance(self.default_sample_rate, (int, float))
            or self.default_sample_rate <= 0
        ):
            raise AudioConfigurationError("Default sample rate must be positive")
        if not isinstance(self.is_default_input, bool) or not isinstance(
            self.is_default_output, bool
        ):
            raise AudioConfigurationError("Default-device flags must be booleans")

    @property
    def direction(self) -> AudioDeviceDirection:
        """Return input, output, or duplex from channel capabilities."""

        if self.max_input_channels and self.max_output_channels:
            return AudioDeviceDirection.DUPLEX
        if self.max_input_channels:
            return AudioDeviceDirection.INPUT

        return AudioDeviceDirection.OUTPUT
