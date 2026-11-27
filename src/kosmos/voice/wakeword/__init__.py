"""Independent wake-word contracts and deterministic activation policy."""

from kosmos.voice.wakeword.activation import WakeWordActivationPolicy
from kosmos.voice.wakeword.config import WakeWordSettings, load_wakeword_settings
from kosmos.voice.wakeword.models import (
    WakeWordDetection,
    WakeWordMetrics,
    WakeWordOperationalState,
    WakeWordResult,
    WakeWordWindow,
)
from kosmos.voice.wakeword.ports import WakeWordDetector

__all__ = [
    "WakeWordActivationPolicy",
    "WakeWordDetection",
    "WakeWordDetector",
    "WakeWordMetrics",
    "WakeWordOperationalState",
    "WakeWordResult",
    "WakeWordSettings",
    "WakeWordWindow",
    "load_wakeword_settings",
]
