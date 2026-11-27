"""Explicit playback boundary for synthesized PCM."""

from kosmos.voice.audio.ports import AudioPlayback
from kosmos.voice.exceptions import AudioPlaybackError
from kosmos.voice.tts.models import SpeechSynthesisResult


def play_synthesis(
    result: SpeechSynthesisResult,
    playback: AudioPlayback,
    *,
    device: int | None = None,
) -> None:
    """Play a completed synthesis only after an explicit caller request."""

    if not playback.play(result.audio, device=device):
        raise AudioPlaybackError("Synthesized audio playback was interrupted")
