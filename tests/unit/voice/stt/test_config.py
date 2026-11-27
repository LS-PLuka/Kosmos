import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from kosmos.voice.exceptions import (
    InvalidSpeechModelError,
    InvalidVoiceConfigurationError,
    SpeechModelUnavailableError,
)
from kosmos.voice.stt.config import STTSettings, load_stt_settings


def _model(tmp_path: Path, *, include: tuple[str, ...] = ()) -> Path:
    path = tmp_path / "base"
    path.mkdir()
    required = {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"} - set(include)
    for name in required:
        if name == "config.json":
            (path / name).write_text(json.dumps({"model_type": "whisper"}), encoding="utf-8")
        else:
            (path / name).write_bytes(b"local")
    return path


def test_stt_is_disabled_and_side_effect_free_by_default() -> None:
    before = os.environ.copy()
    assert load_stt_settings({}) == STTSettings()
    assert os.environ == before


def test_environment_values_are_consumed(tmp_path: Path) -> None:
    settings = load_stt_settings(
        {
            "KOSMOS_STT_ENABLED": "true",
            "KOSMOS_STT_MODEL_PATH": str(tmp_path),
            "KOSMOS_STT_CPU_THREADS": "3",
            "KOSMOS_STT_BEAM_SIZE": "2",
            "KOSMOS_STT_MAX_AUDIO_SECONDS": "10",
        }
    )
    assert settings.enabled and settings.cpu_threads == 3 and settings.max_audio_seconds == 10


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KOSMOS_STT_ENABLED", "maybe"),
        ("KOSMOS_STT_BACKEND", "cloud"),
        ("KOSMOS_STT_CPU_THREADS", "0"),
        ("KOSMOS_STT_BEAM_SIZE", "11"),
        ("KOSMOS_STT_MAX_AUDIO_SECONDS", "nan"),
    ],
)
def test_invalid_settings_are_rejected(name: str, value: str) -> None:
    with pytest.raises(InvalidVoiceConfigurationError):
        load_stt_settings({name: value})


def test_local_model_requires_every_offline_file(tmp_path: Path) -> None:
    path = _model(tmp_path, include=("tokenizer.json",))
    with pytest.raises(SpeechModelUnavailableError, match=r"tokenizer\.json"):
        STTSettings(model_path=path).validate_model()


def test_local_model_rejects_remote_identifier_as_path() -> None:
    with pytest.raises(InvalidSpeechModelError, match="absolute"):
        STTSettings(model_path=Path("Systran/faster-whisper-base")).validate_model()


def test_local_model_validates_whisper_metadata(tmp_path: Path) -> None:
    path = _model(tmp_path)
    (path / "config.json").write_text(json.dumps({"model_type": "other"}), encoding="utf-8")
    with pytest.raises(InvalidSpeechModelError, match="not a Whisper"):
        STTSettings(model_path=path).validate_model()


def test_complete_local_model_returns_identity(tmp_path: Path) -> None:
    model = STTSettings(model_path=_model(tmp_path)).validate_model()
    assert model.identifier == "Systran/faster-whisper-base"
    assert model.path.is_absolute()


def test_settings_are_immutable() -> None:
    settings = STTSettings()
    with pytest.raises(FrozenInstanceError):
        settings.enabled = True  # type: ignore[misc]
