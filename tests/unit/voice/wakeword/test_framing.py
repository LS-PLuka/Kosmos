import pytest

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import InvalidWakeWordInputError
from kosmos.voice.wakeword.framing import WAKE_WORD_AUDIO_FORMAT, WakeWordFramer


def _chunk(frames: int, value: int = 1) -> AudioChunk:
    return AudioChunk(bytes([value, 0]) * frames, WAKE_WORD_AUDIO_FORMAT)


def test_framer_preserves_samples_offsets_and_residual() -> None:
    framer = WakeWordFramer()

    first = framer.push(_chunk(700, 1))
    second = framer.push(_chunk(1_000, 2), start_frame=700)
    residual = framer.finish()

    assert first == ()
    assert len(second) == 1
    assert second[0].start_frame == 0
    assert second[0].audio.data == bytes([1, 0]) * 700 + bytes([2, 0]) * 580
    assert residual is not None
    assert residual.frame_count == 420
    assert residual.data == bytes([2, 0]) * 420


def test_framer_rejects_discontinuity_and_requires_reset() -> None:
    framer = WakeWordFramer()
    framer.push(_chunk(100))

    with pytest.raises(InvalidWakeWordInputError, match="discontinuous"):
        framer.push(_chunk(100), start_frame=101)

    framer.reset()
    assert framer.push(_chunk(1_280), start_frame=0)[0].start_frame == 0


def test_finish_never_pads_residual_audio() -> None:
    framer = WakeWordFramer()
    framer.push(_chunk(17))

    residual = framer.finish()

    assert residual is not None
    assert residual.frame_count == 17
