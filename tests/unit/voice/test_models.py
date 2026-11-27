from dataclasses import FrozenInstanceError

import pytest

from kosmos.voice.audio.models import (
    AudioChunk,
    AudioDevice,
    AudioDeviceDirection,
    AudioFormat,
    SampleFormat,
)
from kosmos.voice.exceptions import AudioConfigurationError


def test_audio_format_exposes_frame_width() -> None:
    audio_format = AudioFormat(16_000, 2)

    assert audio_format.sample_format is SampleFormat.SIGNED_16_LE
    assert audio_format.bytes_per_frame == 4
    assert audio_format.frames_for_duration(0.25) == 4_000


@pytest.mark.parametrize("sample_rate", [True, 0, 7_999, 384_001, 16_000.0])
def test_audio_format_rejects_invalid_sample_rate(sample_rate: object) -> None:
    with pytest.raises(AudioConfigurationError, match="Sample rate"):
        AudioFormat(sample_rate, 1)  # type: ignore[arg-type]


@pytest.mark.parametrize("channels", [True, 0, 33, 1.0])
def test_audio_format_rejects_invalid_channels(channels: object) -> None:
    with pytest.raises(AudioConfigurationError, match="Channel count"):
        AudioFormat(16_000, channels)  # type: ignore[arg-type]


def test_audio_chunk_calculates_frames_and_duration() -> None:
    chunk = AudioChunk(b"\x00\x00" * 8_000, AudioFormat(16_000, 1))

    assert chunk.frame_count == 8_000
    assert chunk.duration_seconds == 0.5


def test_audio_chunk_rejects_partial_frames() -> None:
    with pytest.raises(AudioConfigurationError, match="complete frames"):
        AudioChunk(b"\x00", AudioFormat(16_000, 1))


def test_audio_format_rejects_duration_shorter_than_one_frame() -> None:
    with pytest.raises(AudioConfigurationError, match="at least one PCM frame"):
        AudioFormat(8_000, 1).frames_for_duration(0.000001)


def test_audio_models_are_immutable() -> None:
    audio_format = AudioFormat(16_000, 1)

    with pytest.raises(FrozenInstanceError):
        audio_format.channels = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("inputs", "outputs", "direction"),
    [
        (1, 0, AudioDeviceDirection.INPUT),
        (0, 2, AudioDeviceDirection.OUTPUT),
        (1, 2, AudioDeviceDirection.DUPLEX),
    ],
)
def test_audio_device_derives_direction(
    inputs: int, outputs: int, direction: AudioDeviceDirection
) -> None:
    device = AudioDevice(0, "Device", "Host", inputs, outputs, 48_000)

    assert device.direction is direction


def test_audio_device_rejects_device_without_direction() -> None:
    with pytest.raises(AudioConfigurationError, match="support input or output"):
        AudioDevice(0, "Device", "Host", 0, 0, 48_000)
