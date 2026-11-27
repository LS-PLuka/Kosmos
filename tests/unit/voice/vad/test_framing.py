import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import InvalidVADInputError
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT, AudioFramer


def _chunk(frames: int, *, start: int = 0) -> AudioChunk:
    data = b"".join(((start + index) % 32768).to_bytes(2, "little") for index in range(frames))
    return AudioChunk(data, VAD_AUDIO_FORMAT)


def test_variable_chunks_preserve_order_without_loss_or_duplication() -> None:
    framer = AudioFramer()
    source = _chunk(1_300)
    windows = []
    windows.extend(framer.push(AudioChunk(source.data[:200], VAD_AUDIO_FORMAT)))
    windows.extend(framer.push(AudioChunk(source.data[200:1_800], VAD_AUDIO_FORMAT)))
    windows.extend(framer.push(AudioChunk(source.data[1_800:], VAD_AUDIO_FORMAT)))
    windows.extend(framer.finish())
    assert [window.audio.frame_count for window in windows] == [512, 512, 276]
    assert [window.start_frame for window in windows] == [0, 512, 1_024]
    assert b"".join(window.audio.data for window in windows) == source.data
    assert len(windows[-1].inference_pcm) == 1_024


def test_exact_window_has_no_residual() -> None:
    framer = AudioFramer()
    windows = framer.push(_chunk(512))
    assert len(windows) == 1
    assert framer.finish() == ()
    assert framer.finish() == ()


def test_format_discontinuity_and_use_after_finish_are_rejected() -> None:
    framer = AudioFramer()
    with pytest.raises(InvalidVADInputError, match="requires mono"):
        framer.push(AudioChunk(b"\x00\x00", AudioFormat(8_000, 1)))
    framer.push(_chunk(10))
    with pytest.raises(InvalidVADInputError, match="discontinuity"):
        framer.push(_chunk(10), start_frame=11)
    framer.finish()
    with pytest.raises(InvalidVADInputError, match="finalized"):
        framer.push(_chunk(10))


def test_reset_starts_an_independent_timeline() -> None:
    framer = AudioFramer()
    framer.push(_chunk(20))
    framer.reset()
    assert framer.push(_chunk(512))[0].start_frame == 0
