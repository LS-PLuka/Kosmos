"""Validated configuration for local wake-word detection."""

import hashlib
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kosmos.voice.exceptions import (
    InvalidWakeWordModelError,
    WakeWordModelUnavailableError,
)
from kosmos.voice.wakeword.models import WAKE_WORD_FRAME_SIZE, WAKE_WORD_SAMPLE_RATE

MAX_MODEL_BYTES = 32 * 1024 * 1024
DEFAULT_MODEL_REVISION = "openWakeWord-v0.6.0-c8ef691"


@dataclass(frozen=True, slots=True)
class WakeWordModel:
    """Validated local paths for one openWakeWord-compatible ONNX pipeline."""

    classifier_path: Path
    melspectrogram_path: Path
    embedding_path: Path
    identifier: str


@dataclass(frozen=True, slots=True)
class WakeWordSettings:
    """Side-effect-free wake-word configuration."""

    enabled: bool = False
    backend: str = "openwakeword-onnx"
    phrase: str = "Kosmos"
    model_identifier: str = "kosmos"
    model_revision: str = DEFAULT_MODEL_REVISION
    model_path: Path | None = None
    melspectrogram_path: Path | None = None
    embedding_path: Path | None = None
    model_sha256: str | None = None
    melspectrogram_sha256: str | None = None
    embedding_sha256: str | None = None
    threshold: float = 0.5
    rearm_threshold: float = 0.3
    confirmation_frames: int = 2
    cooldown_seconds: float = 2.0
    warmup_frames: int = 5
    sample_rate: int = WAKE_WORD_SAMPLE_RATE
    frame_size: int = WAKE_WORD_FRAME_SIZE

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise InvalidWakeWordModelError("Wake-word enabled flag must be boolean")
        if self.backend != "openwakeword-onnx":
            raise InvalidWakeWordModelError("Wake-word backend must be openwakeword-onnx")
        for value, name in (
            (self.phrase, "Wake-word phrase"),
            (self.model_identifier, "Model identifier"),
            (self.model_revision, "Model revision"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise InvalidWakeWordModelError(f"{name} must contain 1 to 128 characters")
        for value, name in (
            (self.threshold, "Detection threshold"),
            (self.rearm_threshold, "Rearm threshold"),
            (self.cooldown_seconds, "Cooldown"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise InvalidWakeWordModelError(f"{name} must be a finite number")
        if not 0 < self.threshold <= 1:
            raise InvalidWakeWordModelError(
                "Detection threshold must be greater than zero and at most one"
            )
        if not 0 <= self.rearm_threshold < self.threshold:
            raise InvalidWakeWordModelError("Rearm threshold must be below the detection threshold")
        if not 0 <= self.cooldown_seconds <= 60:
            raise InvalidWakeWordModelError("Cooldown must be from zero to 60 seconds")
        for value, name, minimum, maximum in (
            (self.confirmation_frames, "Confirmation frames", 1, 20),
            (self.warmup_frames, "Warm-up frames", 0, 100),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise InvalidWakeWordModelError(
                    f"{name} must be an integer from {minimum} to {maximum}"
                )
        if self.sample_rate != WAKE_WORD_SAMPLE_RATE or self.frame_size != WAKE_WORD_FRAME_SIZE:
            raise InvalidWakeWordModelError(
                "Wake-word PCM contract must remain 16000 Hz and 1280 frames"
            )
        for checksum in (
            self.model_sha256,
            self.melspectrogram_sha256,
            self.embedding_sha256,
        ):
            if checksum is not None and (
                len(checksum) != 64
                or any(character not in "0123456789abcdef" for character in checksum)
            ):
                raise InvalidWakeWordModelError("Model checksums must be lowercase SHA-256 values")

    @property
    def cooldown_frames(self) -> int:
        return round(self.cooldown_seconds * self.sample_rate)

    def validate_model(self) -> WakeWordModel:
        paths = (
            (self.model_path, self.model_sha256, "classifier"),
            (self.melspectrogram_path, self.melspectrogram_sha256, "melspectrogram"),
            (self.embedding_path, self.embedding_sha256, "embedding"),
        )
        for path, checksum, label in paths:
            self._validate_artifact(path, checksum, label)
        assert self.model_path is not None
        assert self.melspectrogram_path is not None
        assert self.embedding_path is not None
        return WakeWordModel(
            classifier_path=self.model_path,
            melspectrogram_path=self.melspectrogram_path,
            embedding_path=self.embedding_path,
            identifier=self.model_identifier,
        )

    @staticmethod
    def _validate_artifact(path: Path | None, checksum: str | None, label: str) -> None:
        if path is None:
            raise WakeWordModelUnavailableError(f"Wake-word {label} model path is not configured")
        if not path.is_absolute() or path.suffix.lower() != ".onnx":
            raise InvalidWakeWordModelError(
                f"Wake-word {label} model must be an absolute ONNX path"
            )
        if not path.is_file():
            raise WakeWordModelUnavailableError(f"Wake-word {label} model is unavailable")
        size = path.stat().st_size
        if size <= 0 or size > MAX_MODEL_BYTES:
            raise InvalidWakeWordModelError(f"Wake-word {label} model size is invalid")
        if checksum is not None and hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise InvalidWakeWordModelError(f"Wake-word {label} model checksum does not match")


def load_wakeword_settings(environ: Mapping[str, str] | None = None) -> WakeWordSettings:
    """Load wake-word settings without touching models or optional dependencies."""

    source = os.environ if environ is None else environ
    return WakeWordSettings(
        enabled=_boolean(source.get("KOSMOS_WAKEWORD_ENABLED", "false")),
        backend=source.get("KOSMOS_WAKEWORD_BACKEND", "openwakeword-onnx"),
        phrase=source.get("KOSMOS_WAKEWORD_PHRASE", "Kosmos"),
        model_identifier=source.get("KOSMOS_WAKEWORD_MODEL_IDENTIFIER", "kosmos"),
        model_path=_path(source.get("KOSMOS_WAKEWORD_MODEL_PATH")),
        melspectrogram_path=_path(source.get("KOSMOS_WAKEWORD_MELSPECTROGRAM_PATH")),
        embedding_path=_path(source.get("KOSMOS_WAKEWORD_EMBEDDING_MODEL_PATH")),
        model_sha256=source.get("KOSMOS_WAKEWORD_MODEL_SHA256"),
        melspectrogram_sha256=source.get("KOSMOS_WAKEWORD_MELSPECTROGRAM_SHA256"),
        embedding_sha256=source.get("KOSMOS_WAKEWORD_EMBEDDING_MODEL_SHA256"),
        threshold=_float(source.get("KOSMOS_WAKEWORD_THRESHOLD", "0.5"), "threshold"),
        rearm_threshold=_float(
            source.get("KOSMOS_WAKEWORD_REARM_THRESHOLD", "0.3"), "rearm threshold"
        ),
        confirmation_frames=_integer(
            source.get("KOSMOS_WAKEWORD_CONFIRMATION_FRAMES", "2"), "confirmation frames"
        ),
        cooldown_seconds=_float(source.get("KOSMOS_WAKEWORD_COOLDOWN_SECONDS", "2"), "cooldown"),
    )


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise InvalidWakeWordModelError("Wake-word enabled flag is invalid")


def _float(value: str, name: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise InvalidWakeWordModelError(f"Wake-word {name} is invalid") from error


def _integer(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise InvalidWakeWordModelError(f"Wake-word {name} is invalid") from error


def _path(value: str | None) -> Path | None:
    return None if value is None or not value.strip() else Path(value)
