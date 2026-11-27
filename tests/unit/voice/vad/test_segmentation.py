import pytest

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import InvalidSpeechSegmentError
from kosmos.voice.vad.config import VADSettings
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT
from kosmos.voice.vad.models import (
    AudioWindow,
    SpeechEventType,
    UtteranceEndReason,
    VoiceActivityResult,
)
from kosmos.voice.vad.segmentation import DeterministicSpeechSegmenter, SegmentationState


def _settings(**overrides: object) -> VADSettings:
    values: dict[str, object] = {
        "min_speech_ms": 64,
        "min_silence_ms": 64,
        "pre_roll_ms": 32,
        "post_roll_ms": 32,
    }
    values.update(overrides)
    return VADSettings(**values)  # type: ignore[arg-type]


def _input(
    index: int, probability: float, frames: int = 512
) -> tuple[AudioWindow, VoiceActivityResult]:
    start = index * 512
    window = AudioWindow(AudioChunk(bytes([index % 255, 0]) * frames, VAD_AUDIO_FORMAT), start)
    result = VoiceActivityResult(probability, start, frames, 0.001)
    return window, result


def test_continuous_silence_emits_nothing() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    for index in range(5):
        assert segmenter.accept(*_input(index, 0.1)).events == ()
    assert segmenter.finish().events == ()


def test_confirmed_speech_preserves_pre_roll_and_bounded_post_roll() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    segmenter.accept(*_input(0, 0.1))
    segmenter.accept(*_input(1, 0.8))
    started = segmenter.accept(*_input(2, 0.8))
    assert started.events[0].type is SpeechEventType.SPEECH_STARTED
    assert started.events[0].frame == 512
    segmenter.accept(*_input(3, 0.1))
    completed = segmenter.accept(*_input(4, 0.1))
    utterance = completed.utterances[0]
    assert utterance.start_frame == 0
    assert utterance.speech_start_frame == 512
    assert utterance.speech_end_frame == 1_536
    assert utterance.end_frame == 2_048
    assert utterance.end_reason is UtteranceEndReason.SILENCE
    assert [event.type for event in completed.events] == [
        SpeechEventType.SPEECH_ENDED,
        SpeechEventType.UTTERANCE_COMPLETED,
    ]


def test_short_pause_and_hysteresis_band_do_not_split_speech() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    segmenter.accept(*_input(0, 0.8))
    segmenter.accept(*_input(1, 0.8))
    segmenter.accept(*_input(2, 0.2))
    assert segmenter.state is SegmentationState.POSSIBLE_END
    assert segmenter.accept(*_input(3, 0.4)).utterances == ()
    assert segmenter.accept(*_input(4, 0.5)).utterances == ()
    assert segmenter.state is SegmentationState.SPEECH_ACTIVE


def test_isolated_peak_is_cancelled_without_started_event() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    assert segmenter.accept(*_input(0, 0.8)).events == ()
    assert segmenter.accept(*_input(1, 0.1)).events == ()
    assert segmenter.state is SegmentationState.IDLE


def test_stream_end_completes_active_speech_and_discards_candidate() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    segmenter.accept(*_input(0, 0.8))
    discarded = segmenter.finish()
    assert discarded.events[0].type is SpeechEventType.UTTERANCE_DISCARDED

    segmenter.reset()
    segmenter.accept(*_input(0, 0.8))
    segmenter.accept(*_input(1, 0.8))
    completed = segmenter.finish()
    assert completed.utterances[0].end_reason is UtteranceEndReason.STREAM_ENDED


def test_maximum_duration_splits_exactly_without_silent_truncation() -> None:
    settings = _settings(min_speech_ms=32, max_utterance_seconds=0.1, pre_roll_ms=0)
    segmenter = DeterministicSpeechSegmenter(settings)
    completed = None
    for index in range(4):
        result = segmenter.accept(*_input(index, 0.8))
        if result.utterances:
            completed = result
    assert completed is not None
    utterance = completed.utterances[0]
    assert utterance.audio.frame_count == 1_600
    assert utterance.end_reason is UtteranceEndReason.MAX_DURATION


def test_discontinuity_and_mismatched_result_are_rejected() -> None:
    segmenter = DeterministicSpeechSegmenter(_settings())
    with pytest.raises(InvalidSpeechSegmentError, match="discontinuous"):
        segmenter.accept(*_input(1, 0.1))

    window, _result = _input(0, 0.1)
    wrong = VoiceActivityResult(0.1, 1, 512, 0.001)
    with pytest.raises(InvalidSpeechSegmentError, match="does not match"):
        DeterministicSpeechSegmenter(_settings()).accept(window, wrong)
