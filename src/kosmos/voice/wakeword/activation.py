"""Deterministic wake-word activation policy on the acoustic timeline."""

from kosmos.voice.wakeword.config import WakeWordSettings
from kosmos.voice.wakeword.models import (
    WakeWordActivationState,
    WakeWordDetection,
    WakeWordResult,
)


class WakeWordActivationPolicy:
    """Confirm scores, suppress duplicates, and require an explicit low-score rearm."""

    def __init__(self, settings: WakeWordSettings) -> None:
        self._settings = settings
        self.reset()

    @property
    def state(self) -> WakeWordActivationState:
        return self._state

    @property
    def suppressed_detection_count(self) -> int:
        return self._suppressed_detection_count

    def accept(self, result: WakeWordResult) -> WakeWordDetection | None:
        if self._last_frame is not None and result.start_frame != self._last_frame:
            self.reset()
        self._last_frame = result.end_frame

        if not result.ready:
            self._candidate_frames = 0
            return None

        if self._state is WakeWordActivationState.COOLDOWN:
            if result.end_frame < self._cooldown_until_frame:
                if result.score >= self._settings.threshold:
                    self._suppressed_detection_count += 1
                return None
            self._state = WakeWordActivationState.REARM

        if self._state is WakeWordActivationState.REARM:
            if result.score <= self._settings.rearm_threshold:
                self._state = WakeWordActivationState.ARMED
            elif result.score >= self._settings.threshold:
                self._suppressed_detection_count += 1
            return None

        if result.score < self._settings.threshold:
            self._candidate_frames = 0
            self._state = WakeWordActivationState.ARMED
            return None

        self._candidate_frames += 1
        self._state = WakeWordActivationState.POSSIBLE_ACTIVATION
        if self._candidate_frames < self._settings.confirmation_frames:
            return None

        self._candidate_frames = 0
        self._state = WakeWordActivationState.COOLDOWN
        self._cooldown_until_frame = result.end_frame + self._settings.cooldown_frames
        return WakeWordDetection(
            phrase=self._settings.phrase,
            model_identifier=self._settings.model_identifier,
            score=result.score,
            detection_frame=result.end_frame,
        )

    def reset(self) -> None:
        self._state = WakeWordActivationState.ARMED
        self._candidate_frames = 0
        self._cooldown_until_frame = 0
        self._last_frame: int | None = None
        self._suppressed_detection_count = 0
