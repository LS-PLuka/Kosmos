from dataclasses import FrozenInstanceError

import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import InvalidRecognitionRequestError, InvalidTranscriptionResultError
from kosmos.voice.stt.models import (
    SpeechRecognitionMetrics,
    SpeechRecognitionRequest,
    SpeechRecognitionResult,
    SpeechRecognitionStatus,
    TranscriptionSegment,
)


def _metrics(**overrides: object) -> SpeechRecognitionMetrics:
    values: dict[str, object] = {
        "backend": "faster-whisper",
        "model_identifier": "base",
        "device": "cpu",
        "compute_type": "int8",
        "configured_language": "pt",
        "audio_duration_seconds": 1.0,
        "audio_frames": 16_000,
        "audio_bytes": 32_000,
        "model_loading_seconds": 0.1,
        "recognition_seconds": 0.2,
        "total_seconds": 0.3,
        "segment_count": 1,
        "transcript_characters": 4,
        "model_reused": False,
    }
    values.update(overrides)
    return SpeechRecognitionMetrics(**values)  # type: ignore[arg-type]


def test_request_accepts_audio_chunk() -> None:
    audio = AudioChunk(b"\x01\x00", AudioFormat(16_000, 1))
    assert SpeechRecognitionRequest(audio).audio is audio


def test_request_rejects_empty_audio() -> None:
    with pytest.raises(InvalidRecognitionRequestError, match="contain PCM"):
        SpeechRecognitionRequest(AudioChunk(b"", AudioFormat(16_000, 1)))


@pytest.mark.parametrize(
    ("start", "end", "probability"),
    [(float("nan"), 1.0, 0.1), (2.0, 1.0, 0.1), (0.0, 1.0, 1.1)],
)
def test_segment_rejects_invalid_values(start: float, end: float, probability: float) -> None:
    with pytest.raises(InvalidTranscriptionResultError):
        TranscriptionSegment(start, end, "Olá", -0.2, probability)


def test_transcribed_result_requires_content() -> None:
    with pytest.raises(InvalidTranscriptionResultError, match="requires text"):
        SpeechRecognitionResult(
            SpeechRecognitionStatus.TRANSCRIBED,
            "",
            "pt",
            (),
            _metrics(segment_count=0, transcript_characters=0),
        )


def test_no_transcription_result_is_normal() -> None:
    result = SpeechRecognitionResult(
        SpeechRecognitionStatus.NO_TRANSCRIPTION,
        "",
        "pt",
        (),
        _metrics(segment_count=0, transcript_characters=0),
    )
    assert result.status is SpeechRecognitionStatus.NO_TRANSCRIPTION


def test_metrics_expose_measured_real_time_factor() -> None:
    assert _metrics().real_time_factor == pytest.approx(0.2)


def test_models_are_immutable() -> None:
    segment = TranscriptionSegment(0.0, 1.0, "Olá", -0.2, 0.1)
    with pytest.raises(FrozenInstanceError):
        segment.text = "changed"  # type: ignore[misc]
