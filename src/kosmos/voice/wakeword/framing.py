"""Bounded framing for 80 ms wake-word inference windows."""

from kosmos.voice.audio.models import AudioChunk, AudioFormat, SampleFormat
from kosmos.voice.exceptions import InvalidWakeWordInputError
from kosmos.voice.wakeword.models import (
    WAKE_WORD_FRAME_SIZE,
    WAKE_WORD_SAMPLE_RATE,
    WakeWordWindow,
)

WAKE_WORD_AUDIO_FORMAT = AudioFormat(
    sample_rate=WAKE_WORD_SAMPLE_RATE,
    channels=1,
    sample_format=SampleFormat.SIGNED_16_LE,
)


class WakeWordFramer:
    """Preserve variable input chunks while emitting complete ordered windows."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._buffer_start_frame = 0
        self._next_input_frame = 0

    @property
    def residual_frame_count(self) -> int:
        return len(self._buffer) // WAKE_WORD_AUDIO_FORMAT.bytes_per_frame

    def push(
        self, chunk: AudioChunk, *, start_frame: int | None = None
    ) -> tuple[WakeWordWindow, ...]:
        self._validate_chunk(chunk)
        actual_start = self._next_input_frame if start_frame is None else start_frame
        if isinstance(actual_start, bool) or not isinstance(actual_start, int) or actual_start < 0:
            raise InvalidWakeWordInputError("Chunk start frame must be a non-negative integer")
        if actual_start != self._next_input_frame:
            raise InvalidWakeWordInputError(
                "Wake-word audio timeline is discontinuous; reset is required"
            )
        if not self._buffer:
            self._buffer_start_frame = actual_start

        self._buffer.extend(chunk.data)
        self._next_input_frame += chunk.frame_count
        window_bytes = WAKE_WORD_FRAME_SIZE * WAKE_WORD_AUDIO_FORMAT.bytes_per_frame
        windows = []
        while len(self._buffer) >= window_bytes:
            data = bytes(self._buffer[:window_bytes])
            del self._buffer[:window_bytes]
            windows.append(
                WakeWordWindow(
                    AudioChunk(data, WAKE_WORD_AUDIO_FORMAT),
                    start_frame=self._buffer_start_frame,
                )
            )
            self._buffer_start_frame += WAKE_WORD_FRAME_SIZE
        return tuple(windows)

    def finish(self) -> AudioChunk | None:
        """Return real residual audio without padding or inference."""

        if not self._buffer:
            return None
        residual = AudioChunk(bytes(self._buffer), WAKE_WORD_AUDIO_FORMAT)
        self._buffer.clear()
        self._buffer_start_frame = self._next_input_frame
        return residual

    def reset(self) -> None:
        self._buffer.clear()
        self._buffer_start_frame = 0
        self._next_input_frame = 0

    @staticmethod
    def _validate_chunk(chunk: AudioChunk) -> None:
        if chunk.format != WAKE_WORD_AUDIO_FORMAT:
            raise InvalidWakeWordInputError("Wake-word input requires mono 16000 Hz PCM S16LE")
