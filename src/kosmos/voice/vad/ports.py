"""Backend-independent ports for voice activity and segmentation."""

from typing import Protocol

from kosmos.voice.vad.models import (
    AudioWindow,
    SegmentationResult,
    VoiceActivityMetrics,
    VoiceActivityResult,
    VoiceActivityState,
)


class VoiceActivityDetector(Protocol):
    def is_available(self) -> bool: ...

    def load(self) -> None: ...

    def evaluate(self, window: AudioWindow) -> VoiceActivityResult: ...

    @property
    def state(self) -> VoiceActivityState: ...

    @property
    def metrics(self) -> VoiceActivityMetrics: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...


class SpeechSegmenter(Protocol):
    def accept(self, window: AudioWindow, activity: VoiceActivityResult) -> SegmentationResult: ...

    def finish(self) -> SegmentationResult: ...

    def discard(self) -> SegmentationResult: ...

    def reset(self) -> None: ...
