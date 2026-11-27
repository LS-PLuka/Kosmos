"""Side-effect-free configuration and explicit Razo metadata validation."""

import hashlib
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kosmos.voice.audio.models import AudioFormat
from kosmos.voice.exceptions import (
    InvalidVoiceConfigurationError,
    VoiceModelUnavailableError,
)
from kosmos.voice.tts.models import MAX_SYNTHESIZED_AUDIO_BYTES

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_STDERR_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class TTSSettings:
    """Validated configuration for one external Piper installation and voice."""

    enabled: bool = False
    backend: str = "piper"
    executable: Path | None = None
    model_path: Path | None = None
    config_path: Path | None = None
    voice_identifier: str = "razo"
    length_scale: float = 1.0
    volume: float = 1.0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_audio_bytes: int = MAX_SYNTHESIZED_AUDIO_BYTES
    max_stderr_bytes: int = DEFAULT_MAX_STDERR_BYTES
    model_sha256: str | None = None
    config_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise InvalidVoiceConfigurationError("TTS enabled must be a boolean")
        if self.backend != "piper":
            raise InvalidVoiceConfigurationError("TTS backend must be 'piper'")
        if not self.voice_identifier.strip() or len(self.voice_identifier) > 128:
            raise InvalidVoiceConfigurationError(
                "Voice identifier must contain 1 to 128 characters"
            )
        _bounded_number(self.length_scale, "Length scale", 0.1, 10.0)
        _bounded_number(self.volume, "Volume", 0.0, 10.0)
        _bounded_number(self.timeout_seconds, "TTS timeout", 0.1, 300.0)
        _bounded_integer(self.max_audio_bytes, "Maximum audio bytes", MAX_SYNTHESIZED_AUDIO_BYTES)
        _bounded_integer(self.max_stderr_bytes, "Maximum stderr bytes", 1024 * 1024)
        _checksum(self.model_sha256, "Model SHA-256")
        _checksum(self.config_sha256, "Config SHA-256")

    def load_voice_metadata(self) -> "VoiceMetadata":
        """Read and validate configured files only when explicitly requested."""

        if self.model_path is None or self.config_path is None:
            raise VoiceModelUnavailableError("TTS model and config paths must be configured")
        for path, name in ((self.model_path, "model"), (self.config_path, "config")):
            if not path.is_file():
                raise VoiceModelUnavailableError(f"Configured TTS {name} file is unavailable")

        _verify_checksum(self.model_path, self.model_sha256, "model")
        _verify_checksum(self.config_path, self.config_sha256, "config")
        try:
            values = json.loads(self.config_path.read_text(encoding="utf-8"))
            sample_rate = values["audio"]["sample_rate"]
            language = values.get("language", {}).get("code")
            num_speakers = values["num_speakers"]
            values["espeak"]["voice"]
            values["phoneme_id_map"]
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise InvalidVoiceConfigurationError(
                "TTS voice config is not valid Piper JSON metadata"
            ) from error

        if isinstance(num_speakers, bool) or not isinstance(num_speakers, int) or num_speakers < 1:
            raise InvalidVoiceConfigurationError("TTS voice config has invalid speaker metadata")
        try:
            audio_format = AudioFormat(sample_rate, 1)
        except Exception as error:
            raise InvalidVoiceConfigurationError(
                "TTS voice config has an invalid sample rate"
            ) from error
        if language is not None and not isinstance(language, str):
            raise InvalidVoiceConfigurationError("TTS voice config has invalid language metadata")

        return VoiceMetadata(audio_format, language, num_speakers)


@dataclass(frozen=True, slots=True)
class VoiceMetadata:
    """Piper metadata required to interpret raw synthesis output."""

    audio_format: AudioFormat
    language: str | None
    speaker_count: int


def load_tts_settings(environment: Mapping[str, str] | None = None) -> TTSSettings:
    """Load TTS settings without opening files, devices, or processes."""

    values = dict(os.environ if environment is None else environment)
    return TTSSettings(
        enabled=_boolean(values.get("KOSMOS_TTS_ENABLED", "false")),
        backend=values.get("KOSMOS_TTS_BACKEND", "piper").strip().lower(),
        executable=_path(values.get("KOSMOS_TTS_PIPER_EXECUTABLE")),
        model_path=_path(values.get("KOSMOS_TTS_MODEL_PATH")),
        config_path=_path(values.get("KOSMOS_TTS_CONFIG_PATH")),
        voice_identifier=values.get("KOSMOS_TTS_VOICE", "razo").strip(),
        length_scale=_float(values.get("KOSMOS_TTS_LENGTH_SCALE", "1.0"), "Length scale"),
        volume=_float(values.get("KOSMOS_TTS_VOLUME", "1.0"), "Volume"),
        timeout_seconds=_float(
            values.get("KOSMOS_TTS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)), "TTS timeout"
        ),
        model_sha256=_optional(values.get("KOSMOS_TTS_MODEL_SHA256")),
        config_sha256=_optional(values.get("KOSMOS_TTS_CONFIG_SHA256")),
    )


def sha256_file(path: Path) -> str:
    """Calculate a local artifact checksum without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)

    return digest.hexdigest()


def _verify_checksum(path: Path, expected: str | None, label: str) -> None:
    if expected is not None and sha256_file(path) != expected:
        raise InvalidVoiceConfigurationError(f"Configured TTS {label} SHA-256 does not match")


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise InvalidVoiceConfigurationError("TTS enabled must be a boolean")


def _float(value: str, name: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise InvalidVoiceConfigurationError(f"{name} must be numeric") from None


def _path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()


def _optional(value: str | None) -> str | None:
    return value.strip().lower() if value is not None and value.strip() else None


def _bounded_number(value: object, name: str, minimum: float, maximum: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise InvalidVoiceConfigurationError(
            f"{name} must be finite and from {minimum:g} to {maximum:g}"
        )


def _bounded_integer(value: object, name: str, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise InvalidVoiceConfigurationError(f"{name} must be an integer from 1 to {maximum}")


def _checksum(value: str | None, name: str) -> None:
    if value is not None and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
        raise InvalidVoiceConfigurationError(f"{name} must be 64 lowercase hexadecimal characters")
