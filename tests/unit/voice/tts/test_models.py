from dataclasses import FrozenInstanceError

import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import (
    InvalidSynthesisRequestError,
    InvalidSynthesizedAudioError,
)
from kosmos.voice.tts.models import (
    MAX_TEXT_CHARACTERS,
    SpeechSynthesisMetrics,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    SpeechSynthesisSettings,
    SpeechVoice,
)


def test_request_accepts_bounded_portuguese_text() -> None:
    request = SpeechSynthesisRequest("Olá, senhor.", SpeechVoice("razo", "pt-BR"))

    assert request.text == "Olá, senhor."
    assert request.settings == SpeechSynthesisSettings()


@pytest.mark.parametrize("text", ["", "   ", "x" * (MAX_TEXT_CHARACTERS + 1)])
def test_request_rejects_empty_or_excessive_text(text: str) -> None:
    with pytest.raises(InvalidSynthesisRequestError):
        SpeechSynthesisRequest(text, SpeechVoice("razo"))


@pytest.mark.parametrize(
    ("field", "value"),
    [("length_scale", True), ("length_scale", float("nan")), ("volume", -0.1)],
)
def test_settings_reject_invalid_numbers(field: str, value: object) -> None:
    values = {"length_scale": 1.0, "volume": 1.0, field: value}

    with pytest.raises(InvalidSynthesisRequestError):
        SpeechSynthesisSettings(**values)  # type: ignore[arg-type]


def test_result_validates_pcm_and_metrics() -> None:
    audio = AudioChunk(b"\x00\x00" * 22_050, AudioFormat(22_050, 1))
    metrics = SpeechSynthesisMetrics("piper", "razo", 5, 0.25, 1.0, 22_050, 22_050, 44_100)
    result = SpeechSynthesisResult(audio, metrics)

    assert result.metrics.real_time_factor == 0.25


def test_result_rejects_empty_pcm() -> None:
    metrics = SpeechSynthesisMetrics("piper", "razo", 5, 0.25, 1.0, 22_050, 1, 2)

    with pytest.raises(InvalidSynthesizedAudioError, match="contain PCM"):
        SpeechSynthesisResult(AudioChunk(b"", AudioFormat(22_050, 1)), metrics)


def test_models_are_immutable() -> None:
    voice = SpeechVoice("razo")

    with pytest.raises(FrozenInstanceError):
        voice.identifier = "other"  # type: ignore[misc]
