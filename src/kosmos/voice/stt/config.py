"""Side-effect-free STT configuration and local model validation."""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kosmos.voice.exceptions import (
    InvalidSpeechModelError,
    InvalidVoiceConfigurationError,
    SpeechModelUnavailableError,
)

DEFAULT_MODEL_IDENTIFIER = "Systran/faster-whisper-base"
DEFAULT_MODEL_REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")


@dataclass(frozen=True, slots=True)
class SpeechRecognitionModel:
    """Validated identity and location of one local CTranslate2 model."""

    identifier: str
    revision: str
    path: Path


@dataclass(frozen=True, slots=True)
class STTSettings:
    """Validated controls consumed by the Faster Whisper adapter."""

    enabled: bool = False
    backend: str = "faster-whisper"
    model_path: Path | None = None
    model_identifier: str = DEFAULT_MODEL_IDENTIFIER
    model_revision: str = DEFAULT_MODEL_REVISION
    language: str = "pt"
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 4
    workers: int = 1
    beam_size: int = 1
    max_audio_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise InvalidVoiceConfigurationError("STT enabled must be a boolean")
        if self.backend != "faster-whisper":
            raise InvalidVoiceConfigurationError("STT backend must be 'faster-whisper'")
        if self.device != "cpu" or self.compute_type != "int8":
            raise InvalidVoiceConfigurationError("STT execution must use CPU with INT8 compute")
        if not self.model_identifier.strip() or len(self.model_identifier) > 256:
            raise InvalidVoiceConfigurationError("STT model identifier is invalid")
        if not self.model_revision.strip() or len(self.model_revision) > 128:
            raise InvalidVoiceConfigurationError("STT model revision is invalid")
        if not self.language.strip() or len(self.language) > 16:
            raise InvalidVoiceConfigurationError("STT language is invalid")
        _bounded_integer(self.cpu_threads, "STT CPU threads", 1, 16)
        _bounded_integer(self.workers, "STT workers", 1, 1)
        _bounded_integer(self.beam_size, "STT beam size", 1, 10)
        _bounded_number(self.max_audio_seconds, "Maximum STT audio duration", 0.1, 30.0)

    def validate_model(self) -> SpeechRecognitionModel:
        """Validate all local files before any backend construction can occur."""

        if self.model_path is None:
            raise SpeechModelUnavailableError("A local STT model path must be configured")
        if not self.model_path.is_absolute():
            raise InvalidSpeechModelError("STT model path must be an absolute local path")
        if not self.model_path.is_dir():
            raise SpeechModelUnavailableError("Configured local STT model directory is unavailable")
        for filename in REQUIRED_MODEL_FILES:
            if not (self.model_path / filename).is_file():
                raise SpeechModelUnavailableError(f"Local STT model is missing {filename}")

        try:
            configuration_text = (self.model_path / "config.json").read_text(encoding="utf-8")
            configuration = json.loads(configuration_text)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise InvalidSpeechModelError("Local STT config.json is not valid JSON") from error
        if not isinstance(configuration, dict) or not configuration:
            raise InvalidSpeechModelError("Local STT config.json must contain model metadata")
        model_type = configuration.get("model_type")
        if model_type is not None and str(model_type).lower() != "whisper":
            raise InvalidSpeechModelError("Configured CTranslate2 model is not a Whisper model")

        return SpeechRecognitionModel(
            identifier=self.model_identifier,
            revision=self.model_revision,
            path=self.model_path.resolve(),
        )


def load_stt_settings(environment: Mapping[str, str] | None = None) -> STTSettings:
    """Load STT settings without reading model files or importing optional packages."""

    values = dict(os.environ if environment is None else environment)
    path = values.get("KOSMOS_STT_MODEL_PATH")
    return STTSettings(
        enabled=_boolean(values.get("KOSMOS_STT_ENABLED", "false"), "STT enabled"),
        backend=values.get("KOSMOS_STT_BACKEND", "faster-whisper"),
        model_path=Path(path).expanduser() if path and path.strip() else None,
        model_identifier=values.get("KOSMOS_STT_MODEL_IDENTIFIER", DEFAULT_MODEL_IDENTIFIER),
        model_revision=values.get("KOSMOS_STT_MODEL_REVISION", DEFAULT_MODEL_REVISION),
        language=values.get("KOSMOS_STT_LANGUAGE", "pt"),
        cpu_threads=_integer(values.get("KOSMOS_STT_CPU_THREADS", "4"), "STT CPU threads"),
        beam_size=_integer(values.get("KOSMOS_STT_BEAM_SIZE", "1"), "STT beam size"),
        max_audio_seconds=_number(
            values.get("KOSMOS_STT_MAX_AUDIO_SECONDS", "30"), "Maximum STT audio duration"
        ),
    )


def _boolean(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise InvalidVoiceConfigurationError(f"{name} must be a boolean")


def _integer(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InvalidVoiceConfigurationError(f"{name} must be an integer") from None


def _number(value: str, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise InvalidVoiceConfigurationError(f"{name} must be a number") from None


def _bounded_integer(value: object, name: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidVoiceConfigurationError(f"{name} must be from {minimum} to {maximum}")


def _bounded_number(value: object, name: str, minimum: float, maximum: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not minimum <= value <= maximum
    ):
        raise InvalidVoiceConfigurationError(f"{name} must be from {minimum:g} to {maximum:g}")
