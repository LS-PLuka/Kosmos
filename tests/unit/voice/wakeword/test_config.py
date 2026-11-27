import hashlib

import pytest

from kosmos.voice.exceptions import InvalidWakeWordModelError, WakeWordModelUnavailableError
from kosmos.voice.wakeword.config import WakeWordSettings, load_wakeword_settings


def test_defaults_are_disabled_and_use_official_phrase() -> None:
    settings = load_wakeword_settings({})

    assert settings.enabled is False
    assert settings.phrase == "Kosmos"
    assert settings.threshold == 0.5
    assert settings.rearm_threshold == 0.3
    assert settings.confirmation_frames == 2


def test_environment_is_parsed_without_touching_models() -> None:
    settings = load_wakeword_settings(
        {
            "KOSMOS_WAKEWORD_ENABLED": "true",
            "KOSMOS_WAKEWORD_THRESHOLD": "0.6",
            "KOSMOS_WAKEWORD_REARM_THRESHOLD": "0.2",
            "KOSMOS_WAKEWORD_CONFIRMATION_FRAMES": "3",
        }
    )

    assert settings.enabled is True
    assert settings.threshold == 0.6
    assert settings.confirmation_frames == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [("threshold", float("nan")), ("rearm_threshold", 0.5), ("confirmation_frames", True)],
)
def test_invalid_policy_settings_are_rejected(field: str, value: object) -> None:
    values = {field: value}

    with pytest.raises(InvalidWakeWordModelError):
        WakeWordSettings(**values)


def test_validate_model_requires_all_three_local_artifacts(tmp_path) -> None:
    classifier = tmp_path / "kosmos.onnx"
    classifier.write_bytes(b"classifier")
    settings = WakeWordSettings(model_path=classifier)

    with pytest.raises(WakeWordModelUnavailableError, match="melspectrogram"):
        settings.validate_model()


def test_validate_model_checks_hashes(tmp_path) -> None:
    paths = [tmp_path / name for name in ("kosmos.onnx", "mel.onnx", "embedding.onnx")]
    for path in paths:
        path.write_bytes(path.name.encode())
    settings = WakeWordSettings(
        model_path=paths[0],
        melspectrogram_path=paths[1],
        embedding_path=paths[2],
        model_sha256="0" * 64,
    )

    with pytest.raises(InvalidWakeWordModelError, match="checksum"):
        settings.validate_model()

    valid = WakeWordSettings(
        model_path=paths[0],
        melspectrogram_path=paths[1],
        embedding_path=paths[2],
        model_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(),
    )
    assert valid.validate_model().identifier == "kosmos"
