"""Tests for immutable effort policies and explicit reserved levels."""

import math
from dataclasses import FrozenInstanceError

import pytest

from kosmos.core.exceptions import UnsupportedEffortLevelError
from kosmos.core.orchestration import EffortLevel, EffortPolicy, default_effort_policies
from kosmos.core.orchestration.effort import resolve_effort_policy


def test_default_effort_policies_match_provisional_limits() -> None:
    policies = default_effort_policies()

    assert policies[EffortLevel.INSTANT] == EffortPolicy(
        EffortLevel.INSTANT, False, False, 1, 0, 30
    )
    assert policies[EffortLevel.LOW] == EffortPolicy(EffortLevel.LOW, False, True, 3, 2, 60)
    assert policies[EffortLevel.MEDIUM] == EffortPolicy(EffortLevel.MEDIUM, True, True, 5, 4, 120)
    assert policies[EffortLevel.HIGH] == EffortPolicy(EffortLevel.HIGH, True, True, 8, 8, 240)


@pytest.mark.parametrize("level", [EffortLevel.EXPERT, EffortLevel.AUTO])
def test_reserved_effort_levels_are_explicitly_unsupported(level: EffortLevel) -> None:
    with pytest.raises(UnsupportedEffortLevelError):
        resolve_effort_policy(level, default_effort_policies())


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("max_inferences", True, TypeError),
        ("max_inferences", 0, ValueError),
        ("max_tool_calls", -1, ValueError),
        ("deadline_seconds", math.inf, ValueError),
        ("deadline_seconds", 0, ValueError),
    ],
)
def test_effort_policy_rejects_invalid_limits(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    values = {
        "level": EffortLevel.LOW,
        "thinking": False,
        "tools_enabled": True,
        "max_inferences": 3,
        "max_tool_calls": 2,
        "deadline_seconds": 60,
    }
    values[field] = value

    with pytest.raises(error):
        EffortPolicy(**values)


def test_disabled_tools_require_zero_budget() -> None:
    with pytest.raises(ValueError, match="zero tool-call"):
        EffortPolicy(EffortLevel.INSTANT, False, False, 1, 1, 30)


def test_effort_policy_is_immutable() -> None:
    policy = default_effort_policies()[EffortLevel.LOW]

    with pytest.raises(FrozenInstanceError):
        policy.thinking = True
