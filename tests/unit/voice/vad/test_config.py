import hashlib
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from kosmos.voice.exceptions import InvalidVADModelError, InvalidVoiceConfigurationError
from kosmos.voice.vad.config import VADSettings, load_vad_settings


def test_vad_is_disabled_and_side_effect_free_by_default() -> None:
    before = os.environ.copy()
    assert load_vad_settings({}) == VADSettings()
    assert os.environ == before


def test_environment_values_are_consumed(tmp_path: Path) -> None:
    settings = load_vad_settings(
        {
            "KOSMOS_VAD_ENABLED": "true",
            "KOSMOS_VAD_MODEL_PATH": str(tmp_path / "model.onnx"),
            "KOSMOS_VAD_SPEECH_THRESHOLD": "0.6",
            "KOSMOS_VAD_END_SPEECH_THRESHOLD": "0.3",
            "KOSMOS_VAD_PRE_ROLL_MS": "64",
        }
    )
    assert settings.enabled
    assert settings.speech_threshold == 0.6
    assert settings.pre_roll_frames == 1_024


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KOSMOS_VAD_ENABLED", "maybe"),
        ("KOSMOS_VAD_BACKEND", "cloud"),
        ("KOSMOS_VAD_SPEECH_THRESHOLD", "nan"),
        ("KOSMOS_VAD_END_SPEECH_THRESHOLD", "0.5"),
        ("KOSMOS_VAD_MIN_SPEECH_MS", "0"),
        ("KOSMOS_VAD_MIN_SILENCE_MS", "10001"),
        ("KOSMOS_VAD_MAX_UTTERANCE_SECONDS", "31"),
        ("KOSMOS_VAD_MODEL_SHA256", "invalid"),
    ],
)
def test_invalid_environment_settings_are_rejected(name: str, value: str) -> None:
    with pytest.raises(InvalidVoiceConfigurationError):
        load_vad_settings({name: value})


def test_model_validation_checks_extension_size_and_checksum(tmp_path: Path) -> None:
    model = tmp_path / "silero.onnx"
    model.write_bytes(b"official-model-reference")
    checksum = hashlib.sha256(model.read_bytes()).hexdigest()
    metadata = VADSettings(model_path=model, model_sha256=checksum).validate_model()
    assert metadata.path == model.resolve()
    assert metadata.sha256 == checksum

    with pytest.raises(InvalidVADModelError, match="SHA-256"):
        VADSettings(model_path=model, model_sha256="0" * 64).validate_model()


def test_relative_model_path_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("model.onnx").write_bytes(b"model")
    with pytest.raises(InvalidVADModelError, match="absolute"):
        VADSettings(model_path=Path("model.onnx")).validate_model()


def test_settings_are_immutable() -> None:
    settings = VADSettings()
    with pytest.raises(FrozenInstanceError):
        settings.enabled = True  # type: ignore[misc]
