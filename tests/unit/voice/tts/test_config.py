import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from kosmos.voice.exceptions import InvalidVoiceConfigurationError, VoiceModelUnavailableError
from kosmos.voice.tts.config import TTSSettings, load_tts_settings, sha256_file


def _voice_files(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "pt-BR-razo-medium.onnx"
    config = tmp_path / "config.json"
    model.write_bytes(b"onnx")
    config.write_text(
        json.dumps(
            {
                "audio": {"sample_rate": 22050},
                "language": {"code": "pt-br"},
                "num_speakers": 1,
                "espeak": {"voice": "pt-br"},
                "phoneme_id_map": {"_": [0]},
            }
        ),
        encoding="utf-8",
    )
    return model, config


def test_tts_is_disabled_and_side_effect_free_by_default() -> None:
    before = os.environ.copy()

    settings = load_tts_settings({})

    assert settings == TTSSettings()
    assert settings.enabled is False
    assert os.environ == before


def test_load_settings_consumes_supported_environment(tmp_path: Path) -> None:
    model, config = _voice_files(tmp_path)
    settings = load_tts_settings(
        {
            "KOSMOS_TTS_ENABLED": "true",
            "KOSMOS_TTS_PIPER_EXECUTABLE": "piper",
            "KOSMOS_TTS_MODEL_PATH": str(model),
            "KOSMOS_TTS_CONFIG_PATH": str(config),
            "KOSMOS_TTS_LENGTH_SCALE": "1.2",
            "KOSMOS_TTS_VOLUME": "0.8",
            "KOSMOS_TTS_TIMEOUT_SECONDS": "10",
        }
    )

    assert settings.enabled
    assert settings.length_scale == 1.2
    assert settings.volume == 0.8
    assert settings.timeout_seconds == 10


def test_voice_metadata_reads_real_sample_rate(tmp_path: Path) -> None:
    model, config = _voice_files(tmp_path)

    metadata = TTSSettings(model_path=model, config_path=config).load_voice_metadata()

    assert metadata.audio_format.sample_rate == 22_050
    assert metadata.audio_format.channels == 1
    assert metadata.language == "pt-br"


def test_voice_metadata_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(VoiceModelUnavailableError, match="unavailable"):
        TTSSettings(
            model_path=tmp_path / "missing.onnx", config_path=tmp_path / "missing.json"
        ).load_voice_metadata()


def test_voice_metadata_rejects_invalid_json(tmp_path: Path) -> None:
    model = tmp_path / "voice.onnx"
    config = tmp_path / "config.json"
    model.write_bytes(b"onnx")
    config.write_text("not-json", encoding="utf-8")

    with pytest.raises(InvalidVoiceConfigurationError, match="Piper JSON"):
        TTSSettings(model_path=model, config_path=config).load_voice_metadata()


def test_voice_metadata_verifies_configured_checksum(tmp_path: Path) -> None:
    model, config = _voice_files(tmp_path)
    settings = TTSSettings(
        model_path=model,
        config_path=config,
        model_sha256=sha256_file(model),
        config_sha256="0" * 64,
    )

    with pytest.raises(InvalidVoiceConfigurationError, match="config SHA-256"):
        settings.load_voice_metadata()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KOSMOS_TTS_ENABLED", "sometimes"),
        ("KOSMOS_TTS_BACKEND", "cloud"),
        ("KOSMOS_TTS_LENGTH_SCALE", "nan"),
        ("KOSMOS_TTS_VOLUME", "-1"),
        ("KOSMOS_TTS_TIMEOUT_SECONDS", "0"),
    ],
)
def test_load_settings_rejects_invalid_values(name: str, value: str) -> None:
    with pytest.raises(InvalidVoiceConfigurationError):
        load_tts_settings({name: value})


def test_tts_settings_are_immutable() -> None:
    settings = TTSSettings()

    with pytest.raises(FrozenInstanceError):
        settings.enabled = True  # type: ignore[misc]
