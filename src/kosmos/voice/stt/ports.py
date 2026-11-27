"""Backend-independent speech recognition port."""

from typing import Protocol

from kosmos.voice.stt.models import SpeechRecognitionRequest, SpeechRecognitionResult


class SpeechRecognizer(Protocol):
    """Recognize one bounded local PCM request at a time."""

    @property
    def backend(self) -> str: ...

    def is_available(self) -> bool: ...

    async def load(self) -> None: ...

    async def recognize(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult: ...

    async def close(self) -> None: ...
