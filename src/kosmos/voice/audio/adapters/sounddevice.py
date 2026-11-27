"""SoundDevice/PortAudio adapter loaded only for explicit audio operations."""

from collections.abc import Mapping, Sequence
from importlib import import_module
from threading import RLock
from types import ModuleType
from typing import Protocol, cast

from kosmos.voice.audio.buffers import BoundedAudioBuffer
from kosmos.voice.audio.models import AudioChunk, AudioDevice, AudioFormat, SampleFormat
from kosmos.voice.exceptions import (
    AudioBackendUnavailableError,
    AudioCaptureError,
    AudioConfigurationError,
    AudioDeviceNotFoundError,
    AudioPlaybackError,
)
from kosmos.voice.models import VoiceOperationalState


class _InputStream(Protocol):
    def start(self) -> object: ...

    def read(self, frames: int) -> tuple[object, bool]: ...

    def stop(self) -> object: ...

    def close(self) -> object: ...


class _OutputStream(Protocol):
    def start(self) -> object: ...

    def write(self, data: bytes) -> bool: ...

    def stop(self) -> object: ...

    def abort(self) -> object: ...

    def close(self) -> object: ...


class _Defaults(Protocol):
    device: Sequence[int]


class SoundDeviceBackend(Protocol):
    """Small subset of SoundDevice used by the adapter and deterministic fakes."""

    default: _Defaults

    def query_devices(self) -> Sequence[Mapping[str, object]]: ...

    def query_hostapis(self) -> Sequence[Mapping[str, object]]: ...

    def check_input_settings(
        self, *, device: int, channels: int, dtype: str, samplerate: int
    ) -> None: ...

    def check_output_settings(
        self, *, device: int, channels: int, dtype: str, samplerate: int
    ) -> None: ...

    def RawInputStream(
        self,
        *,
        samplerate: int,
        blocksize: int,
        device: int,
        channels: int,
        dtype: str,
    ) -> _InputStream: ...

    def RawOutputStream(
        self, *, samplerate: int, device: int, channels: int, dtype: str
    ) -> _OutputStream: ...


def load_sounddevice_backend() -> SoundDeviceBackend:
    """Import the optional backend and translate dependency or native-library failures."""

    try:
        module = import_module("sounddevice")
    except ModuleNotFoundError as error:
        if error.name != "sounddevice":
            raise AudioBackendUnavailableError(
                "SoundDevice could not load one of its runtime dependencies"
            ) from error
        raise AudioBackendUnavailableError(
            "Voice support is not installed; install the 'voice' extra"
        ) from error
    except (ImportError, OSError) as error:
        raise AudioBackendUnavailableError(
            "SoundDevice is installed, but the native PortAudio backend is unavailable"
        ) from error

    return cast(SoundDeviceBackend, cast(ModuleType, module))


class SoundDeviceDiscovery:
    """Discover and validate process-local PortAudio devices."""

    def __init__(self, backend: SoundDeviceBackend | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> SoundDeviceBackend:
        if self._backend is None:
            self._backend = load_sounddevice_backend()

        return self._backend

    def list_devices(self) -> tuple[AudioDevice, ...]:
        """Return devices without opening input or output streams."""

        try:
            raw_devices = self.backend.query_devices()
            host_apis = self.backend.query_hostapis()
            defaults = tuple(self.backend.default.device)
        except AudioBackendUnavailableError:
            raise
        except Exception as error:
            raise AudioBackendUnavailableError("PortAudio device discovery failed") from error

        default_input = defaults[0] if defaults and defaults[0] >= 0 else None
        default_output = defaults[1] if len(defaults) > 1 and defaults[1] >= 0 else None
        devices = []
        for index, raw_device in enumerate(raw_devices):
            input_channels = _integer_field(raw_device, "max_input_channels")
            output_channels = _integer_field(raw_device, "max_output_channels")
            if input_channels == 0 and output_channels == 0:
                continue

            host_api_index = _integer_field(raw_device, "hostapi")
            try:
                host_api = str(host_apis[host_api_index]["name"])
            except (IndexError, KeyError, TypeError) as error:
                raise AudioBackendUnavailableError(
                    "PortAudio returned invalid host API metadata"
                ) from error
            devices.append(
                AudioDevice(
                    index=index,
                    name=str(raw_device.get("name", "")).strip(),
                    host_api=host_api.strip(),
                    max_input_channels=input_channels,
                    max_output_channels=output_channels,
                    default_sample_rate=_number_field(raw_device, "default_samplerate"),
                    is_default_input=index == default_input,
                    is_default_output=index == default_output,
                )
            )

        return tuple(devices)

    def default_input(self) -> AudioDevice | None:
        return next((device for device in self.list_devices() if device.is_default_input), None)

    def default_output(self) -> AudioDevice | None:
        return next((device for device in self.list_devices() if device.is_default_output), None)

    def validate_input(self, device: int | None, audio_format: AudioFormat) -> None:
        selected = self._select(device, input_device=True)
        if selected.max_input_channels < audio_format.channels:
            raise AudioConfigurationError("Input device does not support the requested channels")

        try:
            self.backend.check_input_settings(
                device=selected.index,
                channels=audio_format.channels,
                dtype=_dtype(audio_format.sample_format),
                samplerate=audio_format.sample_rate,
            )
        except Exception as error:
            raise AudioConfigurationError(
                "Input device does not support the requested PCM format"
            ) from error

    def validate_output(self, device: int | None, audio_format: AudioFormat) -> None:
        selected = self._select(device, input_device=False)
        if selected.max_output_channels < audio_format.channels:
            raise AudioConfigurationError("Output device does not support the requested channels")

        try:
            self.backend.check_output_settings(
                device=selected.index,
                channels=audio_format.channels,
                dtype=_dtype(audio_format.sample_format),
                samplerate=audio_format.sample_rate,
            )
        except Exception as error:
            raise AudioConfigurationError(
                "Output device does not support the requested PCM format"
            ) from error

    def resolve_input(self, device: int | None) -> AudioDevice:
        return self._select(device, input_device=True)

    def resolve_output(self, device: int | None) -> AudioDevice:
        return self._select(device, input_device=False)

    def _select(self, index: int | None, *, input_device: bool) -> AudioDevice:
        devices = self.list_devices()
        if index is None:
            is_default = (
                (lambda candidate: candidate.is_default_input)
                if input_device
                else (lambda candidate: candidate.is_default_output)
            )
            selected = next(
                (device for device in devices if is_default(device)),
                None,
            )
            direction = "input" if input_device else "output"
            if selected is None:
                raise AudioDeviceNotFoundError(f"No default {direction} device is available")
            return selected

        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise AudioDeviceNotFoundError("Device index must be a non-negative integer")

        selected = next((device for device in devices if device.index == index), None)
        if selected is None:
            raise AudioDeviceNotFoundError(f"Audio device {index} was not found")

        supported_channels = (
            selected.max_input_channels if input_device else selected.max_output_channels
        )
        if supported_channels == 0:
            direction = "input" if input_device else "output"
            raise AudioDeviceNotFoundError(f"Audio device {index} is not an {direction} device")

        return selected


class SoundDeviceCapture:
    """Perform one explicitly enabled, duration-bounded blocking capture."""

    def __init__(
        self,
        *,
        voice_enabled: bool,
        duration_limit_seconds: float = 30.0,
        backend: SoundDeviceBackend | None = None,
    ) -> None:
        if (
            isinstance(duration_limit_seconds, bool)
            or not isinstance(duration_limit_seconds, (int, float))
            or not 0 < duration_limit_seconds <= 30
        ):
            raise AudioConfigurationError(
                "Capture duration limit must be greater than zero and at most 30 seconds"
            )
        self._enabled = voice_enabled
        self._duration_limit_seconds = duration_limit_seconds
        self._discovery = SoundDeviceDiscovery(backend)
        self.state = VoiceOperationalState.IDLE

    def capture(
        self,
        *,
        duration_seconds: float,
        audio_format: AudioFormat,
        device: int | None = None,
        block_size: int = 1_024,
    ) -> AudioChunk:
        if not self._enabled:
            raise AudioCaptureError(
                "Voice capture is disabled; set KOSMOS_VOICE_ENABLED=true explicitly"
            )
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or not 0 < duration_seconds <= self._duration_limit_seconds
        ):
            raise AudioCaptureError(
                f"Capture duration must be greater than zero and at most "
                f"{self._duration_limit_seconds:g} seconds"
            )
        if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size <= 0:
            raise AudioCaptureError("Capture block size must be a positive integer")

        selected = self._discovery.resolve_input(device)
        self._discovery.validate_input(selected.index, audio_format)
        frame_count = audio_format.frames_for_duration(duration_seconds)
        buffer = BoundedAudioBuffer(
            audio_format, max_bytes=frame_count * audio_format.bytes_per_frame
        )
        stream = None
        self.state = VoiceOperationalState.CAPTURING
        try:
            stream = self._discovery.backend.RawInputStream(
                samplerate=audio_format.sample_rate,
                blocksize=block_size,
                device=selected.index,
                channels=audio_format.channels,
                dtype=_dtype(audio_format.sample_format),
            )
            stream.start()
            remaining = frame_count
            while remaining:
                requested = min(block_size, remaining)
                data, overflowed = stream.read(requested)
                if overflowed:
                    raise AudioCaptureError("Audio input overflowed during capture")

                chunk = AudioChunk(bytes(data), audio_format)
                if chunk.frame_count != requested:
                    raise AudioCaptureError("Audio backend returned an incomplete input block")
                buffer.append(chunk)
                remaining -= requested

            result = buffer.to_chunk()
            self.state = VoiceOperationalState.IDLE
            return result
        except AudioCaptureError:
            self.state = VoiceOperationalState.ERROR
            raise
        except Exception as error:
            self.state = VoiceOperationalState.ERROR
            raise AudioCaptureError("Audio capture failed") from error
        finally:
            if stream is not None:
                close_error = _close_stream(stream)
                if close_error is not None and self.state is not VoiceOperationalState.ERROR:
                    self.state = VoiceOperationalState.ERROR
                    raise AudioCaptureError(
                        "Audio capture stream could not close safely"
                    ) from close_error

    def close(self) -> None:
        self.state = VoiceOperationalState.CLOSED


class SoundDevicePlayback:
    """Perform blocking PCM playback with explicit abort of the active stream."""

    def __init__(self, backend: SoundDeviceBackend | None = None) -> None:
        self._discovery = SoundDeviceDiscovery(backend)
        self._lock = RLock()
        self._stream: _OutputStream | None = None
        self._interrupted = False
        self.state = VoiceOperationalState.IDLE

    def play(self, chunk: AudioChunk, *, device: int | None = None) -> bool:
        if not chunk.data:
            raise AudioPlaybackError("Audio playback requires at least one PCM frame")

        selected = self._discovery.resolve_output(device)
        self._discovery.validate_output(selected.index, chunk.format)
        self.state = VoiceOperationalState.PLAYING
        stream = None
        try:
            stream = self._discovery.backend.RawOutputStream(
                samplerate=chunk.format.sample_rate,
                device=selected.index,
                channels=chunk.format.channels,
                dtype=_dtype(chunk.format.sample_format),
            )
            with self._lock:
                self._stream = stream
                self._interrupted = False
            stream.start()
            underflowed = stream.write(chunk.data)
            if underflowed:
                raise AudioPlaybackError("Audio output underflowed during playback")

            with self._lock:
                completed = not self._interrupted
            self.state = VoiceOperationalState.IDLE
            return completed
        except AudioPlaybackError:
            self.state = VoiceOperationalState.ERROR
            raise
        except Exception as error:
            self.state = VoiceOperationalState.ERROR
            raise AudioPlaybackError("Audio playback failed") from error
        finally:
            with self._lock:
                self._stream = None
            if stream is not None:
                close_error = _close_stream(stream)
                if close_error is not None and self.state is not VoiceOperationalState.ERROR:
                    self.state = VoiceOperationalState.ERROR
                    raise AudioPlaybackError(
                        "Audio playback stream could not close safely"
                    ) from close_error

    def stop(self) -> bool:
        with self._lock:
            if self._stream is None:
                return False
            self._interrupted = True
            try:
                self._stream.abort()
            except Exception as error:
                raise AudioPlaybackError("Audio playback interruption failed") from error
            return True

    def close(self) -> None:
        self.stop()
        self.state = VoiceOperationalState.CLOSED


def _dtype(sample_format: SampleFormat) -> str:
    if sample_format is SampleFormat.SIGNED_16_LE:
        return "int16"

    raise AudioConfigurationError("Sample format is not supported by SoundDevice")


def _integer_field(values: Mapping[str, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AudioBackendUnavailableError(f"PortAudio returned invalid {key} metadata")
    return value


def _number_field(values: Mapping[str, object], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise AudioBackendUnavailableError(f"PortAudio returned invalid {key} metadata")
    return float(value)


def _close_stream(stream: _InputStream | _OutputStream) -> Exception | None:
    failure = None
    try:
        stream.stop()
    except Exception as error:
        failure = error
    try:
        stream.close()
    except Exception as error:
        if failure is None:
            failure = error

    return failure
