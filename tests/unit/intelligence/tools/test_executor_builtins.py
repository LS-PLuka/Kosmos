"""Tests for authorization, execution, and the approved pure tools."""

import asyncio

import pytest

from kosmos.intelligence.tools import (
    CALCULATE_DEFINITION,
    ToolAuthorization,
    ToolCall,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
    ToolResultStatus,
    ToolRisk,
    create_builtin_registry,
)


def _execute(
    executor: ToolExecutor,
    call: ToolCall,
    *allowed: str,
):
    return asyncio.run(executor.execute(call, ToolAuthorization(allowed)))


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        ("add", 5, 3, 8),
        ("subtract", 5, 8, -3),
        ("multiply", 125, 32, 4_000),
        ("divide", 7, 2, 3.5),
        ("divide", 8, 2, 4.0),
    ],
)
def test_calculate_operations(
    operation: str,
    a: int,
    b: int,
    expected: int | float,
) -> None:
    executor = ToolExecutor(create_builtin_registry())
    call = ToolCall("call_1", "calculate", {"operation": operation, "a": a, "b": b})

    result = _execute(executor, call, "calculate")

    assert result.status is ToolResultStatus.SUCCESS
    assert result.data == {"result": expected}


def test_count_items_supports_empty_and_populated_arrays() -> None:
    executor = ToolExecutor(create_builtin_registry())

    empty = _execute(
        executor,
        ToolCall("call_1", "count_items", {"items": []}),
        "count_items",
    )
    populated = _execute(
        executor,
        ToolCall("call_2", "count_items", {"items": ["Java", "Python", "Go"]}),
        "count_items",
    )

    assert empty.data == {"count": 0}
    assert populated.data == {"count": 3}


def test_authorization_denies_by_default_before_argument_validation() -> None:
    calls = 0
    registry = ToolRegistry()

    def handler(arguments):
        nonlocal calls
        calls += 1
        return {"ok": True}

    registry.register(CALCULATE_DEFINITION, handler)
    executor = ToolExecutor(registry)
    invalid = ToolCall("call_1", "calculate", {})

    result = _execute(executor, invalid)

    assert result.status is ToolResultStatus.UNAUTHORIZED
    assert calls == 0


def test_authorization_is_isolated_per_execution() -> None:
    executor = ToolExecutor(create_builtin_registry())
    call = ToolCall("call_1", "count_items", {"items": []})

    denied = _execute(executor, call, "calculate")
    allowed = _execute(executor, call, "count_items")

    assert denied.status is ToolResultStatus.UNAUTHORIZED
    assert allowed.status is ToolResultStatus.SUCCESS


@pytest.mark.parametrize(
    "risk",
    [ToolRisk.READ_ONLY, ToolRisk.SIDE_EFFECT, ToolRisk.SENSITIVE],
)
def test_non_pure_risk_classes_remain_blocked_even_when_allowed(risk: ToolRisk) -> None:
    registry = ToolRegistry()
    definition = ToolDefinition("blocked", "Blocked test tool.", (), risk)
    registry.register(definition, lambda arguments: {"executed": True})

    result = _execute(ToolExecutor(registry), ToolCall("call_1", "blocked", {}), "blocked")

    assert result.status is ToolResultStatus.UNAUTHORIZED


def test_unknown_invalid_and_handler_failures_have_distinct_results() -> None:
    executor = ToolExecutor(create_builtin_registry())

    unknown = _execute(executor, ToolCall("call_1", "unknown", {}), "unknown")
    invalid = _execute(executor, ToolCall("call_2", "calculate", {}), "calculate")
    division = _execute(
        executor,
        ToolCall("call_3", "calculate", {"operation": "divide", "a": 1, "b": 0}),
        "calculate",
    )

    assert unknown.status is ToolResultStatus.UNKNOWN_TOOL
    assert invalid.status is ToolResultStatus.INVALID_ARGUMENTS
    assert division.status is ToolResultStatus.EXECUTION_FAILED
    assert "zero" not in (division.message or "")


def test_authorization_flags_in_arguments_are_rejected_and_never_reach_handler() -> None:
    calls = 0
    registry = ToolRegistry()

    def handler(arguments):
        nonlocal calls
        calls += 1
        return {"ok": True}

    registry.register(CALCULATE_DEFINITION, handler)
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "add", "a": 1, "b": 2, "authorized": True},
    )

    result = _execute(ToolExecutor(registry), call, "calculate")

    assert result.status is ToolResultStatus.INVALID_ARGUMENTS
    assert calls == 0


def test_non_serializable_and_oversized_results_fail_safely() -> None:
    for result_value in (object(), "x" * 20_000):
        registry = ToolRegistry()
        registry.register(CALCULATE_DEFINITION, lambda arguments, value=result_value: value)
        executor = ToolExecutor(registry)
        call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})

        result = _execute(executor, call, "calculate")

        assert result.status is ToolResultStatus.EXECUTION_FAILED
        assert result.data is None


def test_async_handler_runs_once_without_retry() -> None:
    calls = 0
    registry = ToolRegistry()

    async def handler(arguments):
        nonlocal calls
        calls += 1
        return {"ok": True}

    registry.register(CALCULATE_DEFINITION, handler)
    call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})

    result = _execute(ToolExecutor(registry), call, "calculate")

    assert result.status is ToolResultStatus.SUCCESS
    assert calls == 1


def test_cancellation_propagates() -> None:
    registry = ToolRegistry()

    async def handler(arguments):
        raise asyncio.CancelledError

    registry.register(CALCULATE_DEFINITION, handler)
    call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})

    with pytest.raises(asyncio.CancelledError):
        _execute(ToolExecutor(registry), call, "calculate")
