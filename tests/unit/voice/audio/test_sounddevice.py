from collections.abc import Mapping, Sequence

import pytest

from kosmos.voice.audio.adapters.sounddevice import (
    SoundDeviceCapture,
    SoundDeviceDiscovery,
    SoundDevicePlayback,
)
from kosmos.voice.audio.models import AudioChunk, AudioDeviceDirection, AudioFormat
from kosmos.voice.exceptions import (
    AudioCaptureError,
    AudioConfigurationError,
    AudioDeviceNotFoundError,
    AudioPlaybackError,
)
from kosmos.voice.models import VoiceOperationalState


class FakeDefaults:
    device = (0, 1)


class FakeInputStream:
    def __init__(self, backend: "FakeBackend", channels: int) -> None:
        self.backend = backend
        self.channels = channels
        self.closed = False

    def start(self) -> None:
        self.backend.input_started = True

    def read(self, frames: int) -> tuple[bytes, bool]:
        if self.backend.capture_failure:
            raise RuntimeError("device disconnected")
        return bytes(frames * self.channels * 2), self.backend.overflow

    def stop(self) -> None:
        self.backend.input_stopped = True

    def close(self) -> None:
        self.closed = True
        self.backend.input_closed = True
        if self.backend.close_failure:
            raise RuntimeError("close failed")


class FakeOutputStream:
    def __init__(self, backend: "FakeBackend") -> None:
        self.backend = backend

    def start(self) -> None:
        self.backend.output_started = True

    def write(self, data: bytes) -> bool:
        self.backend.output_data = data
        if self.backend.playback_failure:
            raise RuntimeError("device disconnected")
        return self.backend.underflow

    def stop(self) -> None:
        self.backend.output_stopped = True

    def abort(self) -> None:
        self.backend.output_aborted = True

    def close(self) -> None:
        self.backend.output_closed = True
        if self.backend.close_failure:
            raise RuntimeError("close failed")


class FakeBackend:
    def __init__(self) -> None:
        self.default = FakeDefaults()
        self.devices: list[Mapping[str, object]] = [
            {
                "name": "Microphone",
                "hostapi": 0,
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48_000.0,
            },
            {
                "name": "Speakers",
                "hostapi": 0,
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 48_000.0,
            },
            {
                "name": "Headset",
                "hostapi": 0,
                "max_input_channels": 1,
                "max_output_channels": 2,
                "default_samplerate": 48_000.0,
            },
        ]
        self.unsupported = False
        self.overflow = False
        self.underflow = False
        self.capture_failure = False
        self.playback_failure = False
        self.close_failure = False
        self.input_started = False
        self.input_stopped = False
        self.input_closed = False
        self.output_started = False
        self.output_stopped = False
        self.output_aborted = False
        self.output_closed = False
        self.output_data = b""

    def query_devices(self) -> Sequence[Mapping[str, object]]:
        return self.devices

    def query_hostapis(self) -> Sequence[Mapping[str, object]]:
        return [{"name": "Fake Host"}]

    def check_input_settings(self, **settings: object) -> None:
        if self.unsupported:
            raise ValueError("unsupported")

    def check_output_settings(self, **settings: object) -> None:
        if self.unsupported:
            raise ValueError("unsupported")

    def RawInputStream(self, **settings: object) -> FakeInputStream:
        return FakeInputStream(self, int(settings["channels"]))

    def RawOutputStream(self, **settings: object) -> FakeOutputStream:
        return FakeOutputStream(self)


def test_discovery_reports_defaults_and_duplex_capability() -> None:
    devices = SoundDeviceDiscovery(FakeBackend()).list_devices()

    assert devices[0].is_default_input
    assert devices[1].is_default_output
    assert devices[2].direction is AudioDeviceDirection.DUPLEX


def test_discovery_returns_none_when_defaults_are_absent() -> None:
    backend = FakeBackend()
    backend.default.device = (-1, -1)
    discovery = SoundDeviceDiscovery(backend)

    assert discovery.default_input() is None
    assert discovery.default_output() is None


def test_discovery_does_not_select_first_device_when_default_is_absent() -> None:
    backend = FakeBackend()
    backend.default.device = (-1, 1)

    with pytest.raises(AudioDeviceNotFoundError, match="No default input"):
        SoundDeviceDiscovery(backend).validate_input(None, AudioFormat(16_000, 1))


def test_discovery_rejects_unknown_or_wrong_direction_device() -> None:
    discovery = SoundDeviceDiscovery(FakeBackend())

    with pytest.raises(AudioDeviceNotFoundError, match="was not found"):
        discovery.validate_input(99, AudioFormat(16_000, 1))
    with pytest.raises(AudioDeviceNotFoundError, match="not an input"):
        discovery.validate_input(1, AudioFormat(16_000, 1))


def test_discovery_translates_unsupported_format() -> None:
    backend = FakeBackend()
    backend.unsupported = True

    with pytest.raises(AudioConfigurationError, match="does not support"):
        SoundDeviceDiscovery(backend).validate_output(1, AudioFormat(48_000, 1))


def test_capture_requires_explicit_voice_activation() -> None:
    backend = FakeBackend()

    with pytest.raises(AudioCaptureError, match="disabled"):
        SoundDeviceCapture(voice_enabled=False, backend=backend).capture(
            duration_seconds=0.1, audio_format=AudioFormat(16_000, 1)
        )

    assert backend.input_started is False


def test_capture_reads_blocks_and_always_closes_stream() -> None:
    backend = FakeBackend()
    capture = SoundDeviceCapture(voice_enabled=True, backend=backend)

    chunk = capture.capture(
        duration_seconds=0.1,
        audio_format=AudioFormat(16_000, 1),
        block_size=512,
    )

    assert chunk.frame_count == 1_600
    assert backend.input_started and backend.input_stopped and backend.input_closed
    assert capture.state is VoiceOperationalState.IDLE


@pytest.mark.parametrize(
    ("attribute", "message"), [("overflow", "overflowed"), ("capture_failure", "failed")]
)
def test_capture_translates_failure_and_closes_stream(attribute: str, message: str) -> None:
    backend = FakeBackend()
    setattr(backend, attribute, True)
    capture = SoundDeviceCapture(voice_enabled=True, backend=backend)

    with pytest.raises(AudioCaptureError, match=message):
        capture.capture(duration_seconds=0.1, audio_format=AudioFormat(16_000, 1))

    assert backend.input_closed
    assert capture.state is VoiceOperationalState.ERROR


def test_capture_enforces_duration_limit() -> None:
    with pytest.raises(AudioCaptureError, match="at most 1"):
        SoundDeviceCapture(
            voice_enabled=True, duration_limit_seconds=1, backend=FakeBackend()
        ).capture(duration_seconds=2, audio_format=AudioFormat(16_000, 1))


def test_playback_writes_pcm_and_closes_stream() -> None:
    backend = FakeBackend()
    player = SoundDevicePlayback(backend)
    chunk = AudioChunk(b"\x01\x00" * 10, AudioFormat(48_000, 1))

    assert player.play(chunk) is True
    assert backend.output_data == chunk.data
    assert backend.output_started and backend.output_stopped and backend.output_closed
    assert player.state is VoiceOperationalState.IDLE


def test_capture_reports_cleanup_failure_after_successful_read() -> None:
    backend = FakeBackend()
    backend.close_failure = True

    with pytest.raises(AudioCaptureError, match="close safely"):
        SoundDeviceCapture(voice_enabled=True, backend=backend).capture(
            duration_seconds=0.1, audio_format=AudioFormat(16_000, 1)
        )

    assert backend.input_closed


@pytest.mark.parametrize(
    ("attribute", "message"), [("underflow", "underflowed"), ("playback_failure", "failed")]
)
def test_playback_translates_failure_and_closes_stream(attribute: str, message: str) -> None:
    backend = FakeBackend()
    setattr(backend, attribute, True)
    player = SoundDevicePlayback(backend)

    with pytest.raises(AudioPlaybackError, match=message):
        player.play(AudioChunk(b"\x00\x00", AudioFormat(48_000, 1)))

    assert backend.output_closed
    assert player.state is VoiceOperationalState.ERROR


def test_playback_stop_is_safe_when_idle() -> None:
    assert SoundDevicePlayback(FakeBackend()).stop() is False


def test_playback_rejects_empty_pcm() -> None:
    with pytest.raises(AudioPlaybackError, match="at least one PCM frame"):
        SoundDevicePlayback(FakeBackend()).play(AudioChunk(b"", AudioFormat(48_000, 1)))


def test_playback_reports_cleanup_failure_after_successful_write() -> None:
    backend = FakeBackend()
    backend.close_failure = True

    with pytest.raises(AudioPlaybackError, match="close safely"):
        SoundDevicePlayback(backend).play(AudioChunk(b"\x00\x00", AudioFormat(48_000, 1)))

    assert backend.output_closed
