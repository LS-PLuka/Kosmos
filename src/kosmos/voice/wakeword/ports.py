"""Backend-independent wake-word detector port."""

from typing import Protocol

from kosmos.voice.wakeword.models import (
    WakeWordMetrics,
    WakeWordOperationalState,
    WakeWordResult,
    WakeWordWindow,
)


class WakeWordDetector(Protocol):
    """Synchronous ownership boundary for one ordered PCM stream."""

    @property
    def state(self) -> WakeWordOperationalState: ...

    @property
    def available(self) -> bool: ...

    @property
    def model_identifier(self) -> str: ...

    @property
    def metrics(self) -> WakeWordMetrics: ...

    def load(self) -> None: ...

    def evaluate(self, window: WakeWordWindow) -> WakeWordResult: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...
