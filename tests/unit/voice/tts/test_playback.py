import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import AudioPlaybackError
from kosmos.voice.tts.models import SpeechSynthesisMetrics, SpeechSynthesisResult
from kosmos.voice.tts.playback import play_synthesis


class FakePlayback:
    def __init__(self, completed: bool = True) -> None:
        self.completed = completed
        self.chunk: AudioChunk | None = None
        self.device: int | None = None

    def play(self, chunk: AudioChunk, *, device: int | None = None) -> bool:
        self.chunk = chunk
        self.device = device
        return self.completed

    def stop(self) -> bool:
        return False


def _result() -> SpeechSynthesisResult:
    audio = AudioChunk(b"\x00\x00" * 22_050, AudioFormat(22_050, 1))
    metrics = SpeechSynthesisMetrics("piper", "razo", 5, 0.5, 1.0, 22_050, 22_050, 44_100)
    return SpeechSynthesisResult(audio, metrics)


def test_explicit_playback_uses_synthesized_sample_rate_and_device() -> None:
    playback = FakePlayback()

    play_synthesis(_result(), playback, device=4)

    assert playback.chunk is not None
    assert playback.chunk.format.sample_rate == 22_050
    assert playback.device == 4


def test_interrupted_playback_is_not_reported_as_complete() -> None:
    with pytest.raises(AudioPlaybackError, match="interrupted"):
        play_synthesis(_result(), FakePlayback(completed=False))
