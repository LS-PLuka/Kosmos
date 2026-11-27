"""Explicitly bounded in-memory PCM buffering."""

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import AudioBufferOverflowError, AudioConfigurationError


class BoundedAudioBuffer:
    """Preserve complete PCM frames and reject, rather than discard, overflow."""

    def __init__(self, audio_format: AudioFormat, *, max_bytes: int) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise AudioConfigurationError("Buffer limit must be a positive integer")
        if max_bytes % audio_format.bytes_per_frame:
            raise AudioConfigurationError("Buffer limit must align to complete PCM frames")

        self._format = audio_format
        self._max_bytes = max_bytes
        self._data = bytearray()

    @property
    def format(self) -> AudioFormat:
        return self._format

    @property
    def byte_count(self) -> int:
        return len(self._data)

    @property
    def frame_count(self) -> int:
        return self.byte_count // self._format.bytes_per_frame

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self._format.sample_rate

    def append(self, chunk: AudioChunk) -> None:
        """Append compatible frames or leave the buffer unchanged on overflow."""

        if chunk.format != self._format:
            raise AudioConfigurationError("Audio chunk format does not match the buffer format")
        if self.byte_count + len(chunk.data) > self._max_bytes:
            raise AudioBufferOverflowError("Audio buffer capacity would be exceeded")

        self._data.extend(chunk.data)

    def clear(self) -> None:
        """Release retained PCM bytes for the completed operation."""

        self._data.clear()

    def to_chunk(self) -> AudioChunk:
        """Return an immutable snapshot of buffered PCM frames."""

        return AudioChunk(bytes(self._data), self._format)
