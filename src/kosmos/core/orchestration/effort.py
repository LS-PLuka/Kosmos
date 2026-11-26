"""Immutable Kosmos effort levels and their provisional execution policies."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from kosmos.core.exceptions import UnsupportedEffortLevelError


class EffortLevel(str, Enum):
    """Kosmos-owned effort levels, independent of provider-specific controls."""

    INSTANT = "instant"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXPERT = "expert"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class EffortPolicy:
    """Trusted immutable limits for one supported effort level."""

    level: EffortLevel
    thinking: bool
    tools_enabled: bool
    max_inferences: int
    max_tool_calls: int
    deadline_seconds: float
    streaming_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.level, EffortLevel):
            raise TypeError("level must be an EffortLevel")
        if not isinstance(self.thinking, bool):
            raise TypeError("thinking must be a boolean")
        if not isinstance(self.tools_enabled, bool):
            raise TypeError("tools_enabled must be a boolean")
        if not isinstance(self.streaming_enabled, bool):
            raise TypeError("streaming_enabled must be a boolean")

        for field_name in ("max_inferences", "max_tool_calls"):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")

        if self.max_inferences < 1:
            raise ValueError("max_inferences must be greater than zero")
        if not self.tools_enabled and self.max_tool_calls:
            raise ValueError("disabled tool calling requires a zero tool-call limit")
        if self.tools_enabled and self.max_tool_calls < 1:
            raise ValueError("enabled tool calling requires a positive tool-call limit")
        if isinstance(self.deadline_seconds, bool) or not isinstance(
            self.deadline_seconds, int | float
        ):
            raise TypeError("deadline_seconds must be a number")
        if not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be finite and greater than zero")


def default_effort_policies() -> Mapping[EffortLevel, EffortPolicy]:
    """Return the immutable provisional policies for functional effort levels."""

    policies = {
        EffortLevel.INSTANT: EffortPolicy(EffortLevel.INSTANT, False, False, 1, 0, 30),
        EffortLevel.LOW: EffortPolicy(EffortLevel.LOW, False, True, 3, 2, 60),
        EffortLevel.MEDIUM: EffortPolicy(EffortLevel.MEDIUM, True, True, 5, 4, 120),
        EffortLevel.HIGH: EffortPolicy(EffortLevel.HIGH, True, True, 8, 8, 240),
    }
    return MappingProxyType(policies)


def resolve_effort_policy(
    level: EffortLevel,
    policies: Mapping[EffortLevel, EffortPolicy],
) -> EffortPolicy:
    """Resolve a supported level without silently substituting reserved levels."""

    if not isinstance(level, EffortLevel):
        raise TypeError("effort must be an EffortLevel")
    if level in {EffortLevel.EXPERT, EffortLevel.AUTO}:
        raise UnsupportedEffortLevelError(f"effort level {level.value!r} is not supported")

    try:
        return policies[level]
    except KeyError:
        raise UnsupportedEffortLevelError(
            f"effort level {level.value!r} has no configured policy"
        ) from None
