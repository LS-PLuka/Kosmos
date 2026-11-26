"""Approved pure deterministic tools for Stage 01.5."""

import math
from collections.abc import Mapping

from kosmos.intelligence.tools.models import (
    JSONValue,
    ParameterType,
    ToolDefinition,
    ToolParameter,
)
from kosmos.intelligence.tools.registry import ToolRegistry

MAX_OPERAND_ABS = 1_000_000_000_000
MAX_RESULT_ABS = 1_000_000_000_000_000
MAX_COUNT_ITEMS = 1_000
MAX_ITEM_LENGTH = 200

CALCULATE_DEFINITION = ToolDefinition(
    name="calculate",
    description="Perform one deterministic basic arithmetic operation.",
    parameters=(
        ToolParameter(
            "operation",
            ParameterType.STRING,
            "Arithmetic operation.",
            allowed_values=("add", "subtract", "multiply", "divide"),
        ),
        ToolParameter(
            "a",
            ParameterType.NUMBER,
            "First finite operand.",
            minimum=-MAX_OPERAND_ABS,
            maximum=MAX_OPERAND_ABS,
        ),
        ToolParameter(
            "b",
            ParameterType.NUMBER,
            "Second finite operand.",
            minimum=-MAX_OPERAND_ABS,
            maximum=MAX_OPERAND_ABS,
        ),
    ),
)

COUNT_ITEMS_DEFINITION = ToolDefinition(
    name="count_items",
    description="Count strings in a bounded array.",
    parameters=(
        ToolParameter(
            "items",
            ParameterType.ARRAY,
            "Strings to count.",
            min_items=0,
            max_items=MAX_COUNT_ITEMS,
            items=ToolParameter(
                "item",
                ParameterType.STRING,
                "One item.",
                min_length=0,
                max_length=MAX_ITEM_LENGTH,
            ),
        ),
    ),
)


def calculate(arguments: Mapping[str, object]) -> JSONValue:
    """Perform basic arithmetic without dynamic expression evaluation."""

    operation = arguments["operation"]
    a = arguments["a"]
    b = arguments["b"]

    if not isinstance(operation, str):  # Validated by the executor; narrows types here.
        raise ValueError("operation must be a string")
    if isinstance(a, bool) or not isinstance(a, int | float):
        raise ValueError("a must be a number")
    if isinstance(b, bool) or not isinstance(b, int | float):
        raise ValueError("b must be a number")

    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("division by zero")
        result = a / b
    else:
        raise ValueError("unsupported operation")

    if not math.isfinite(result) or abs(result) > MAX_RESULT_ABS:
        raise ValueError("result exceeds the supported finite range")

    return {"result": result}


def count_items(arguments: Mapping[str, object]) -> JSONValue:
    """Count an already validated array of strings."""

    items = arguments["items"]

    if not isinstance(items, list):
        raise ValueError("items must be an array")

    return {"count": len(items)}


def create_builtin_registry() -> ToolRegistry:
    """Construct a fresh explicit registry containing only approved pure tools."""

    registry = ToolRegistry()
    registry.register(CALCULATE_DEFINITION, calculate)
    registry.register(COUNT_ITEMS_DEFINITION, count_items)
    return registry
