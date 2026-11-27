import math
from dataclasses import FrozenInstanceError

import pytest

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import InvalidSpeechSegmentError, InvalidVoiceActivityResultError
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT
from kosmos.voice.vad.models import (
    AudioWindow,
    Utterance,
    UtteranceEndReason,
    VoiceActivityResult,
)


def test_result_is_finite_bounded_and_immutable() -> None:
    result = VoiceActivityResult(0.5, 0, 512, 0.001)
    with pytest.raises(FrozenInstanceError):
        result.probability = 0.2  # type: ignore[misc]
    for value in (-0.1, 1.1, math.nan, math.inf, True):
        with pytest.raises(InvalidVoiceActivityResultError):
            VoiceActivityResult(value, 0, 512, 0.001)  # type: ignore[arg-type]


def test_residual_window_padding_is_inference_only() -> None:
    window = AudioWindow(AudioChunk(b"\x01\x00" * 10, VAD_AUDIO_FORMAT), 12)
    assert window.audio.frame_count == 10
    assert len(window.inference_pcm) == 1_024
    assert window.end_frame == 22


def test_utterance_timeline_must_match_real_audio() -> None:
    audio = AudioChunk(b"\x01\x00" * 10, VAD_AUDIO_FORMAT)
    with pytest.raises(InvalidSpeechSegmentError, match="does not match"):
        Utterance(1, audio, 0, 11, 0, 10, UtteranceEndReason.STREAM_ENDED)
