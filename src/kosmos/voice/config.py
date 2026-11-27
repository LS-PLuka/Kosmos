"""Side-effect-free Voice Foundation configuration."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from kosmos.voice.audio.models import AudioFormat
from kosmos.voice.exceptions import AudioConfigurationError

DEFAULT_INPUT_SAMPLE_RATE = 16_000
DEFAULT_INPUT_CHANNELS = 1
DEFAULT_BLOCK_SIZE = 1_024
DEFAULT_CAPTURE_DURATION_LIMIT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    """Validated settings consumed by capture and diagnostic operations."""

    enabled: bool = False
    input_device: int | None = None
    output_device: int | None = None
    input_sample_rate: int = DEFAULT_INPUT_SAMPLE_RATE
    input_channels: int = DEFAULT_INPUT_CHANNELS
    block_size: int = DEFAULT_BLOCK_SIZE
    capture_duration_limit_seconds: float = DEFAULT_CAPTURE_DURATION_LIMIT_SECONDS

    def __post_init__(self) -> None:
        AudioFormat(self.input_sample_rate, self.input_channels)
        _positive_integer(self.block_size, "Block size")
        _optional_device(self.input_device, "Input device")
        _optional_device(self.output_device, "Output device")

        if (
            isinstance(self.capture_duration_limit_seconds, bool)
            or not isinstance(self.capture_duration_limit_seconds, (int, float))
            or not 0 < self.capture_duration_limit_seconds <= 30
        ):
            raise AudioConfigurationError(
                "Capture duration limit must be greater than zero and at most 30 seconds"
            )


def load_voice_settings(environment: Mapping[str, str] | None = None) -> VoiceSettings:
    """Load voice settings without mutating the process environment or opening devices."""

    values = dict(os.environ if environment is None else environment)
    return VoiceSettings(
        enabled=_boolean(values.get("KOSMOS_VOICE_ENABLED", "false"), "Voice enabled"),
        input_device=_device(values.get("KOSMOS_VOICE_INPUT_DEVICE"), "Input device"),
        output_device=_device(values.get("KOSMOS_VOICE_OUTPUT_DEVICE"), "Output device"),
        input_sample_rate=_integer(
            values.get("KOSMOS_VOICE_INPUT_SAMPLE_RATE", str(DEFAULT_INPUT_SAMPLE_RATE)),
            "Input sample rate",
        ),
        input_channels=_integer(
            values.get("KOSMOS_VOICE_INPUT_CHANNELS", str(DEFAULT_INPUT_CHANNELS)),
            "Input channels",
        ),
        block_size=_integer(
            values.get("KOSMOS_VOICE_BLOCK_SIZE", str(DEFAULT_BLOCK_SIZE)), "Block size"
        ),
    )


def _boolean(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise AudioConfigurationError(f"{field_name} must be a boolean")


def _integer(value: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise AudioConfigurationError(f"{field_name} must be an integer") from None

    _positive_integer(parsed, field_name)
    return parsed


def _device(value: str | None, field_name: str) -> int | None:
    if value is None or not value.strip():
        return None

    try:
        parsed = int(value)
    except ValueError:
        raise AudioConfigurationError(f"{field_name} must be a non-negative device index") from None

    _optional_device(parsed, field_name)
    return parsed


def _positive_integer(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 1_048_576:
        raise AudioConfigurationError(f"{field_name} must be a positive integer")


def _optional_device(value: object, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AudioConfigurationError(f"{field_name} must be a non-negative device index")
