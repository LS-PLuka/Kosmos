import pytest

from kosmos.voice.audio.buffers import BoundedAudioBuffer
from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import AudioBufferOverflowError, AudioConfigurationError


def test_buffer_preserves_order_size_and_duration() -> None:
    audio_format = AudioFormat(8_000, 1)
    buffer = BoundedAudioBuffer(audio_format, max_bytes=8)

    buffer.append(AudioChunk(b"\x01\x00\x02\x00", audio_format))
    buffer.append(AudioChunk(b"\x03\x00", audio_format))

    assert buffer.to_chunk().data == b"\x01\x00\x02\x00\x03\x00"
    assert buffer.byte_count == 6
    assert buffer.frame_count == 3
    assert buffer.duration_seconds == 3 / 8_000


def test_buffer_rejects_overflow_without_discarding_existing_pcm() -> None:
    audio_format = AudioFormat(16_000, 1)
    buffer = BoundedAudioBuffer(audio_format, max_bytes=4)
    buffer.append(AudioChunk(b"\x01\x00", audio_format))

    with pytest.raises(AudioBufferOverflowError):
        buffer.append(AudioChunk(b"\x02\x00\x03\x00", audio_format))

    assert buffer.to_chunk().data == b"\x01\x00"


def test_buffer_rejects_incompatible_format() -> None:
    buffer = BoundedAudioBuffer(AudioFormat(16_000, 1), max_bytes=4)

    with pytest.raises(AudioConfigurationError, match="does not match"):
        buffer.append(AudioChunk(b"\x00\x00", AudioFormat(48_000, 1)))


def test_buffer_clear_releases_retained_content() -> None:
    audio_format = AudioFormat(16_000, 1)
    buffer = BoundedAudioBuffer(audio_format, max_bytes=4)
    buffer.append(AudioChunk(b"\x00\x00", audio_format))

    buffer.clear()

    assert buffer.to_chunk().data == b""


def test_buffer_limit_must_align_to_frames() -> None:
    with pytest.raises(AudioConfigurationError, match="complete PCM frames"):
        BoundedAudioBuffer(AudioFormat(16_000, 2), max_bytes=3)
