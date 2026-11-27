import math

import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import InvalidWakeWordInputError, InvalidWakeWordResultError
from kosmos.voice.wakeword.models import (
    WakeWordDetection,
    WakeWordResult,
    WakeWordWindow,
)


def test_window_preserves_absolute_timeline() -> None:
    audio = AudioChunk(b"\x00\x00" * 1_280, AudioFormat(16_000, 1))

    window = WakeWordWindow(audio, start_frame=2_560)

    assert window.end_frame == 3_840


@pytest.mark.parametrize("frames", [1_279, 1_281])
def test_window_rejects_non_inference_sized_audio(frames: int) -> None:
    audio = AudioChunk(b"\x00\x00" * frames, AudioFormat(16_000, 1))

    with pytest.raises(InvalidWakeWordInputError):
        WakeWordWindow(audio, start_frame=0)


@pytest.mark.parametrize("score", [-0.1, 1.1, math.nan, math.inf])
def test_result_rejects_invalid_scores(score: float) -> None:
    with pytest.raises(InvalidWakeWordResultError):
        WakeWordResult(score, 0, 1_280, 0.01, True)


def test_detection_derives_timestamp_from_acoustic_frame() -> None:
    detection = WakeWordDetection("Kosmos", "kosmos", 0.8, 8_000)

    assert detection.detection_timestamp_seconds == 0.5
