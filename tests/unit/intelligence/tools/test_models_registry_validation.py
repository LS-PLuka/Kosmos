"""Tests for tool contracts, schemas, registry, and deterministic validation."""

import math

import pytest

from kosmos.intelligence.tools import (
    CALCULATE_DEFINITION,
    COUNT_ITEMS_DEFINITION,
    ParameterType,
    ToolCall,
    ToolDefinition,
    ToolInferenceResponse,
    ToolMessage,
    ToolMessageRole,
    ToolParameter,
    ToolRegistry,
)
from kosmos.intelligence.tools.validation import ToolArgumentError, validate_arguments


def test_definition_builds_compact_schema_from_the_same_parameters() -> None:
    schema = CALCULATE_DEFINITION.to_provider_schema()

    assert schema["function"]["name"] == "calculate"
    assert schema["function"]["parameters"]["required"] == ["operation", "a", "b"]
    assert schema["function"]["parameters"]["additionalProperties"] is False
    assert schema["function"]["parameters"]["properties"]["operation"]["enum"] == [
        "add",
        "subtract",
        "multiply",
        "divide",
    ]
    assert "risk" not in schema
    assert "handler" not in str(schema)


def test_builtin_descriptions_explain_selection_without_duplicating_policy() -> None:
    calculate_schema = CALCULATE_DEFINITION.to_provider_schema()["function"]
    count_schema = COUNT_ITEMS_DEFINITION.to_provider_schema()["function"]

    assert "deterministic" in calculate_schema["description"]
    assert "conceptual explanations" in calculate_schema["description"]
    assert "dividend" in calculate_schema["parameters"]["properties"]["a"]["description"]
    assert (
        "each array element counts as one item"
        in (count_schema["parameters"]["properties"]["items"]["description"])
    )
    assert "authorized" not in str(calculate_schema).lower()


@pytest.mark.parametrize("name", ["", "Calculate", "two-words", "_private", "with space"])
def test_rejects_invalid_tool_and_parameter_names(name: str) -> None:
    with pytest.raises(ValueError):
        ToolDefinition(name, "Description", ())

    with pytest.raises(ValueError):
        ToolParameter(name, ParameterType.STRING, "Description")


def test_rejects_duplicate_parameter_names_and_invalid_constraints() -> None:
    parameter = ToolParameter("value", ParameterType.STRING, "Value")

    with pytest.raises(ValueError, match="unique"):
        ToolDefinition("duplicate", "Description", (parameter, parameter))

    with pytest.raises(ValueError, match="array parameters"):
        ToolParameter("items", ParameterType.ARRAY, "Items")

    with pytest.raises(ValueError, match="numeric limits"):
        ToolParameter("text", ParameterType.STRING, "Text", minimum=1)

    with pytest.raises(TypeError, match="match the parameter type"):
        ToolParameter("choice", ParameterType.INTEGER, "Choice", allowed_values=(True,))


def test_tool_call_deeply_freezes_a_detached_argument_copy() -> None:
    source = {"items": ["one", {"nested": [1, 2]}]}
    call = ToolCall("call_1", "count_items", source)
    source["items"].append("later")

    assert call.arguments["items"] == ("one", {"nested": (1, 2)})

    with pytest.raises(TypeError):
        call.arguments["extra"] = True


def test_tool_call_rejects_non_json_and_excessively_deep_arguments() -> None:
    with pytest.raises(TypeError, match="JSON serializable"):
        ToolCall("call_1", "calculate", {"bad": object()})

    nested: object = "end"

    for _ in range(10):
        nested = [nested]

    with pytest.raises(ValueError, match="maximum depth"):
        ToolCall("call_1", "calculate", {"value": nested})


def test_tool_response_accepts_calls_without_text_and_preserves_order() -> None:
    first = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})
    second = ToolCall("call_2", "count_items", {"items": []})
    response = ToolInferenceResponse("model", "", (first, second))

    assert response.tool_calls == (first, second)
    assert response.as_message().role is ToolMessageRole.ASSISTANT

    with pytest.raises(ValueError, match="text or tool calls"):
        ToolInferenceResponse("model", "", ())


def test_tool_messages_enforce_role_specific_fields() -> None:
    with pytest.raises(ValueError, match="tool name"):
        ToolMessage(ToolMessageRole.TOOL, "result")

    with pytest.raises(ValueError, match="only assistant"):
        ToolMessage(
            ToolMessageRole.USER,
            "request",
            (ToolCall("call_1", "calculate", {}),),
        )


def test_registry_is_explicit_ordered_and_isolated() -> None:
    first = ToolRegistry()
    second = ToolRegistry()

    def handler(arguments):
        return {"ok": True}

    first.register(CALCULATE_DEFINITION, handler)

    assert first.get("calculate").handler is handler
    assert first.definitions() == (CALCULATE_DEFINITION,)
    assert second.definitions() == ()

    with pytest.raises(ValueError, match="already registered"):
        first.register(CALCULATE_DEFINITION, handler)


def test_registry_schema_does_not_expose_handler() -> None:
    registry = ToolRegistry()
    registry.register(CALCULATE_DEFINITION, lambda arguments: arguments)

    schema = registry.provider_schemas()[0]

    assert schema == CALCULATE_DEFINITION.to_provider_schema()
    assert "lambda" not in str(schema)


def test_validation_accepts_valid_values_and_returns_a_detached_copy() -> None:
    arguments = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    ).arguments

    validated = validate_arguments(CALCULATE_DEFINITION, arguments)

    assert validated == {"operation": "multiply", "a": 125, "b": 32}


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"operation": "add", "a": 1}, "required"),
        ({"operation": "add", "a": 1, "b": 2, "extra": 3}, "unknown"),
        ({"operation": "power", "a": 1, "b": 2}, "unsupported"),
        ({"operation": "add", "a": True, "b": 2}, "number"),
        ({"operation": "add", "a": "1", "b": 2}, "number"),
        ({"operation": "add", "a": 1_000_000_000_001, "b": 2}, "maximum"),
    ],
)
def test_validation_rejects_invalid_arguments(
    arguments: dict[str, object],
    message: str,
) -> None:
    call = ToolCall("call_1", "calculate", arguments)

    with pytest.raises(ToolArgumentError, match=message):
        validate_arguments(CALCULATE_DEFINITION, call.arguments)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_models_reject_non_finite_numbers_before_validation(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        ToolCall("call_1", "calculate", {"operation": "add", "a": value, "b": 1})


def test_array_validation_supports_empty_and_bounded_string_items() -> None:
    empty = ToolCall("call_1", "count_items", {"items": []})
    assert validate_arguments(COUNT_ITEMS_DEFINITION, empty.arguments) == {"items": []}

    invalid = ToolCall("call_2", "count_items", {"items": [1]})

    with pytest.raises(ToolArgumentError, match="string"):
        validate_arguments(COUNT_ITEMS_DEFINITION, invalid.arguments)

    oversized = ToolCall("call_3", "count_items", {"items": ["item"] * 1_001})

    with pytest.raises(ToolArgumentError, match="too many"):
        validate_arguments(COUNT_ITEMS_DEFINITION, oversized.arguments)
