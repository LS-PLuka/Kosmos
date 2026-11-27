import os
from dataclasses import FrozenInstanceError

import pytest

from kosmos.voice.config import VoiceSettings, load_voice_settings
from kosmos.voice.exceptions import AudioConfigurationError


def test_voice_settings_are_disabled_by_default() -> None:
    settings = load_voice_settings({})

    assert settings == VoiceSettings()
    assert settings.enabled is False


def test_voice_settings_load_consumed_environment_values() -> None:
    settings = load_voice_settings(
        {
            "KOSMOS_VOICE_ENABLED": "yes",
            "KOSMOS_VOICE_INPUT_DEVICE": "1",
            "KOSMOS_VOICE_OUTPUT_DEVICE": "2",
            "KOSMOS_VOICE_INPUT_SAMPLE_RATE": "48000",
            "KOSMOS_VOICE_INPUT_CHANNELS": "2",
            "KOSMOS_VOICE_BLOCK_SIZE": "512",
        }
    )

    assert settings == VoiceSettings(True, 1, 2, 48_000, 2, 512)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("KOSMOS_VOICE_ENABLED", "maybe", "boolean"),
        ("KOSMOS_VOICE_INPUT_DEVICE", "-1", "non-negative"),
        ("KOSMOS_VOICE_OUTPUT_DEVICE", "speaker", "non-negative"),
        ("KOSMOS_VOICE_INPUT_SAMPLE_RATE", "0", "positive"),
        ("KOSMOS_VOICE_INPUT_CHANNELS", "mono", "integer"),
        ("KOSMOS_VOICE_BLOCK_SIZE", "0", "positive"),
    ],
)
def test_voice_settings_reject_invalid_environment(name: str, value: str, message: str) -> None:
    with pytest.raises(AudioConfigurationError, match=message):
        load_voice_settings({name: value})


def test_voice_settings_load_does_not_mutate_process_environment() -> None:
    before = os.environ.copy()

    load_voice_settings({"KOSMOS_VOICE_ENABLED": "true"})

    assert os.environ == before


def test_voice_settings_are_immutable() -> None:
    settings = VoiceSettings()

    with pytest.raises(FrozenInstanceError):
        settings.enabled = True  # type: ignore[misc]
