"""Backend-independent text-to-speech port."""

from typing import Protocol

from kosmos.voice.tts.models import SpeechSynthesisRequest, SpeechSynthesisResult


class SpeechSynthesizer(Protocol):
    """Synthesize bounded local PCM without selecting an output device."""

    @property
    def backend(self) -> str: ...

    def is_available(self) -> bool: ...

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult: ...

    async def close(self) -> None: ...
