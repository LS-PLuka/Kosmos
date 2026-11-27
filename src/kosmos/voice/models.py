"""Voice-level operational models."""

from enum import StrEnum


class VoiceOperationalState(StrEnum):
    """States exposed by one local audio resource."""

    IDLE = "idle"
    CAPTURING = "capturing"
    PLAYING = "playing"
    ERROR = "error"
    CLOSED = "closed"
