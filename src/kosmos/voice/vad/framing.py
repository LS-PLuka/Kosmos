"""Lossless bounded framing for the fixed Silero inference window."""

from kosmos.voice.audio.models import AudioChunk, AudioFormat, SampleFormat
from kosmos.voice.exceptions import InvalidVADInputError
from kosmos.voice.vad.models import VAD_FRAME_SIZE, VAD_SAMPLE_RATE, AudioWindow

VAD_AUDIO_FORMAT = AudioFormat(VAD_SAMPLE_RATE, 1, SampleFormat.SIGNED_16_LE)


class AudioFramer:
    """Turn variable compatible chunks into ordered fixed-size inference windows."""

    def __init__(self, *, frame_size: int = VAD_FRAME_SIZE) -> None:
        if frame_size != VAD_FRAME_SIZE:
            raise InvalidVADInputError("Silero VAD frame size must be 512 samples")
        self._frame_size = frame_size
        self._window_bytes = frame_size * VAD_AUDIO_FORMAT.bytes_per_frame
        self._pending = bytearray()
        self._emitted_frames = 0
        self._received_frames = 0
        self._finished = False

    @property
    def pending_frames(self) -> int:
        return len(self._pending) // VAD_AUDIO_FORMAT.bytes_per_frame

    @property
    def received_frames(self) -> int:
        return self._received_frames

    def push(self, chunk: AudioChunk, *, start_frame: int | None = None) -> tuple[AudioWindow, ...]:
        """Preserve every sample or reject a format or timeline discontinuity."""

        if self._finished:
            raise InvalidVADInputError("Audio framer is finalized")
        if chunk.format != VAD_AUDIO_FORMAT:
            raise InvalidVADInputError("VAD requires mono 16000 Hz signed 16-bit PCM")
        if chunk.frame_count == 0:
            raise InvalidVADInputError("VAD audio chunk must not be empty")
        if start_frame is not None and start_frame != self._received_frames:
            raise InvalidVADInputError("Audio timeline discontinuity requires an explicit reset")

        windows: list[AudioWindow] = []
        data = memoryview(chunk.data)
        position = 0
        if self._pending:
            needed = self._window_bytes - len(self._pending)
            take = min(needed, len(data))
            self._pending.extend(data[:take])
            position += take
            if len(self._pending) == self._window_bytes:
                windows.append(self._window(bytes(self._pending)))
                self._pending.clear()

        while len(data) - position >= self._window_bytes:
            end = position + self._window_bytes
            windows.append(self._window(bytes(data[position:end])))
            position = end

        self._pending.extend(data[position:])
        self._received_frames += chunk.frame_count
        return tuple(windows)

    def finish(self) -> tuple[AudioWindow, ...]:
        """Return real residual audio once; padding remains inference-only on the window."""

        if self._finished:
            return ()
        self._finished = True
        if not self._pending:
            return ()

        window = self._window(bytes(self._pending))
        self._pending.clear()
        return (window,)

    def reset(self) -> None:
        self._pending.clear()
        self._emitted_frames = 0
        self._received_frames = 0
        self._finished = False

    def _window(self, data: bytes) -> AudioWindow:
        window = AudioWindow(AudioChunk(data, VAD_AUDIO_FORMAT), self._emitted_frames)
        self._emitted_frames = window.end_frame
        return window
