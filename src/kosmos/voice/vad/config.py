"""Side-effect-free configuration for local voice activity detection."""

import hashlib
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kosmos.voice.exceptions import (
    InvalidVADModelError,
    InvalidVoiceConfigurationError,
    VADModelUnavailableError,
)

DEFAULT_MODEL_REVISION = "5cd7945676eb32225748052e2e6a0580e4686a08"
REFERENCE_MODEL_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
MAX_MODEL_BYTES = 32 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True, slots=True)
class VADModel:
    path: Path
    revision: str
    sha256: str | None


@dataclass(frozen=True, slots=True)
class VADSettings:
    """Validated settings that do not load packages, files, models, or devices."""

    enabled: bool = False
    backend: str = "silero"
    model_path: Path | None = None
    model_revision: str = DEFAULT_MODEL_REVISION
    model_sha256: str | None = None
    sample_rate: int = 16_000
    frame_size: int = 512
    speech_threshold: float = 0.5
    end_speech_threshold: float = 0.35
    min_speech_ms: int = 160
    min_silence_ms: int = 640
    pre_roll_ms: int = 256
    post_roll_ms: int = 128
    max_utterance_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise InvalidVoiceConfigurationError("VAD enabled must be a boolean")
        if self.backend != "silero":
            raise InvalidVoiceConfigurationError("VAD backend must be silero")
        if self.sample_rate != 16_000 or self.frame_size != 512:
            raise InvalidVoiceConfigurationError("Silero VAD requires 16000 Hz and 512 frames")
        _probability(self.speech_threshold, "Speech threshold")
        _probability(self.end_speech_threshold, "End speech threshold")
        if self.end_speech_threshold >= self.speech_threshold:
            raise InvalidVoiceConfigurationError(
                "End speech threshold must be lower than speech threshold"
            )
        for value, name, allow_zero, maximum in (
            (self.min_speech_ms, "Minimum speech duration", False, 10_000),
            (self.min_silence_ms, "Minimum silence duration", False, 10_000),
            (self.pre_roll_ms, "Pre-roll duration", True, 10_000),
            (self.post_roll_ms, "Post-roll duration", True, 10_000),
        ):
            _duration(value, name, allow_zero=allow_zero, maximum=maximum)
        _number(self.max_utterance_seconds, "Maximum utterance duration", 0.1, 30.0)
        if self.min_speech_ms / 1000 > self.max_utterance_seconds:
            raise InvalidVoiceConfigurationError(
                "Minimum speech duration must not exceed maximum utterance duration"
            )
        if (self.pre_roll_ms + self.min_speech_ms) / 1000 > self.max_utterance_seconds:
            raise InvalidVoiceConfigurationError(
                "Pre-roll and minimum speech must fit within the utterance limit"
            )
        if self.post_roll_ms / 1000 > self.max_utterance_seconds:
            raise InvalidVoiceConfigurationError(
                "Post-roll must not exceed maximum utterance duration"
            )
        if not self.model_revision.strip():
            raise InvalidVoiceConfigurationError("VAD model revision must not be empty")
        if self.model_sha256 is not None and not _SHA256.fullmatch(self.model_sha256):
            raise InvalidVoiceConfigurationError("VAD model SHA-256 must contain 64 hex digits")

    @property
    def min_speech_frames(self) -> int:
        return math.ceil(self.sample_rate * self.min_speech_ms / 1000)

    @property
    def min_silence_frames(self) -> int:
        return math.ceil(self.sample_rate * self.min_silence_ms / 1000)

    @property
    def pre_roll_frames(self) -> int:
        return round(self.sample_rate * self.pre_roll_ms / 1000)

    @property
    def post_roll_frames(self) -> int:
        return round(self.sample_rate * self.post_roll_ms / 1000)

    @property
    def max_utterance_frames(self) -> int:
        return round(self.sample_rate * self.max_utterance_seconds)

    def validate_model(self) -> VADModel:
        """Validate an explicitly configured local regular ONNX file."""

        if self.model_path is None:
            raise VADModelUnavailableError("No local VAD model path is configured")
        if not self.model_path.is_absolute():
            raise InvalidVADModelError("VAD model path must be absolute")
        if not self.model_path.is_file():
            raise VADModelUnavailableError("Configured local VAD model file is unavailable")
        if self.model_path.suffix.lower() != ".onnx":
            raise InvalidVADModelError("VAD model must be an ONNX file")
        size = self.model_path.stat().st_size
        if size <= 0 or size > MAX_MODEL_BYTES:
            raise InvalidVADModelError("VAD model size is empty or exceeds the 32 MiB limit")
        expected = self.model_sha256.lower() if self.model_sha256 else None
        if expected is not None and _file_sha256(self.model_path) != expected:
            raise InvalidVADModelError("VAD model SHA-256 does not match configuration")

        return VADModel(self.model_path.resolve(), self.model_revision, expected)


def load_vad_settings(environment: Mapping[str, str] | None = None) -> VADSettings:
    """Load VAD settings without touching model files, packages, devices, or the network."""

    values = dict(os.environ if environment is None else environment)
    path = values.get("KOSMOS_VAD_MODEL_PATH")
    checksum = values.get("KOSMOS_VAD_MODEL_SHA256")
    return VADSettings(
        enabled=_boolean(values.get("KOSMOS_VAD_ENABLED", "false"), "VAD enabled"),
        backend=values.get("KOSMOS_VAD_BACKEND", "silero").strip().lower(),
        model_path=Path(path).expanduser() if path and path.strip() else None,
        model_revision=values.get("KOSMOS_VAD_MODEL_REVISION", DEFAULT_MODEL_REVISION),
        model_sha256=checksum.strip().lower() if checksum and checksum.strip() else None,
        speech_threshold=_parse_float(
            values.get("KOSMOS_VAD_SPEECH_THRESHOLD", "0.5"), "Speech threshold"
        ),
        end_speech_threshold=_parse_float(
            values.get("KOSMOS_VAD_END_SPEECH_THRESHOLD", "0.35"),
            "End speech threshold",
        ),
        min_speech_ms=_parse_int(
            values.get("KOSMOS_VAD_MIN_SPEECH_MS", "160"), "Minimum speech duration"
        ),
        min_silence_ms=_parse_int(
            values.get("KOSMOS_VAD_MIN_SILENCE_MS", "640"), "Minimum silence duration"
        ),
        pre_roll_ms=_parse_int(values.get("KOSMOS_VAD_PRE_ROLL_MS", "256"), "Pre-roll"),
        post_roll_ms=_parse_int(values.get("KOSMOS_VAD_POST_ROLL_MS", "128"), "Post-roll"),
        max_utterance_seconds=_parse_float(
            values.get("KOSMOS_VAD_MAX_UTTERANCE_SECONDS", "30"),
            "Maximum utterance duration",
        ),
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _boolean(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise InvalidVoiceConfigurationError(f"{name} must be a boolean")


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InvalidVoiceConfigurationError(f"{name} must be an integer") from None


def _parse_float(value: str, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise InvalidVoiceConfigurationError(f"{name} must be a number") from None


def _duration(value: object, name: str, *, allow_zero: bool, maximum: int) -> None:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidVoiceConfigurationError(f"{name} must be from {minimum} to {maximum} ms")


def _probability(value: object, name: str) -> None:
    _number(value, name, 0.0, 1.0)


def _number(value: object, name: str, minimum: float, maximum: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise InvalidVoiceConfigurationError(f"{name} must be from {minimum:g} to {maximum:g}")
