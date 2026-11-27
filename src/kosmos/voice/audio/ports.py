"""Backend-independent Voice Foundation ports."""

from typing import Protocol

from kosmos.voice.audio.models import AudioChunk, AudioDevice, AudioFormat


class AudioDeviceDiscovery(Protocol):
    """Discover devices and validate explicit audio formats."""

    def list_devices(self) -> tuple[AudioDevice, ...]: ...

    def default_input(self) -> AudioDevice | None: ...

    def default_output(self) -> AudioDevice | None: ...

    def validate_input(self, device: int | None, audio_format: AudioFormat) -> None: ...

    def validate_output(self, device: int | None, audio_format: AudioFormat) -> None: ...


class AudioCapture(Protocol):
    """Capture a bounded PCM chunk after explicit voice activation."""

    def capture(
        self,
        *,
        duration_seconds: float,
        audio_format: AudioFormat,
        device: int | None = None,
        block_size: int = 1_024,
    ) -> AudioChunk: ...


class AudioPlayback(Protocol):
    """Play PCM content and expose explicit interruption."""

    def play(self, chunk: AudioChunk, *, device: int | None = None) -> bool: ...

    def stop(self) -> bool: ...
