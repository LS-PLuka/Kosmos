"""Deterministic argument validation from trusted tool definitions."""

import math
from collections.abc import Mapping

from kosmos.intelligence.tools.models import (
    FrozenJSON,
    ParameterType,
    ToolDefinition,
    ToolParameter,
    thaw_json,
)


class ToolArgumentError(ValueError):
    """Raised when proposed tool arguments violate the advertised schema."""


def validate_arguments(
    definition: ToolDefinition,
    arguments: Mapping[str, FrozenJSON],
) -> dict[str, object]:
    """Validate arguments without coercion and return one detached handler copy."""

    if not isinstance(definition, ToolDefinition):
        raise TypeError("definition must be a ToolDefinition")
    if not isinstance(arguments, Mapping):
        raise ToolArgumentError("arguments must be an object")

    parameters = {parameter.name: parameter for parameter in definition.parameters}
    unknown = set(arguments) - set(parameters)

    if unknown:
        raise ToolArgumentError("arguments contain unknown fields")

    missing = {
        parameter.name
        for parameter in definition.parameters
        if parameter.required and parameter.name not in arguments
    }

    if missing:
        raise ToolArgumentError("required arguments are missing")

    validated: dict[str, object] = {}

    for name, value in arguments.items():
        validated[name] = _validate_value(parameters[name], value)

    return validated


def _validate_value(parameter: ToolParameter, frozen_value: FrozenJSON) -> object:
    value = thaw_json(frozen_value)
    parameter_type = parameter.type

    if parameter_type is ParameterType.STRING:
        if not isinstance(value, str):
            raise ToolArgumentError(f"{parameter.name} must be a string")
        _validate_length(parameter, len(value))
    elif parameter_type is ParameterType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolArgumentError(f"{parameter.name} must be an integer")
        _validate_number(parameter, value)
    elif parameter_type is ParameterType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ToolArgumentError(f"{parameter.name} must be a number")
        if not math.isfinite(value):
            raise ToolArgumentError(f"{parameter.name} must be finite")
        _validate_number(parameter, value)
    elif parameter_type is ParameterType.BOOLEAN:
        if not isinstance(value, bool):
            raise ToolArgumentError(f"{parameter.name} must be a boolean")
    elif parameter_type is ParameterType.ARRAY:
        if not isinstance(value, list):
            raise ToolArgumentError(f"{parameter.name} must be an array")
        _validate_items(parameter, value)
    else:  # pragma: no cover - enum exhaustiveness guard
        raise ToolArgumentError("unsupported parameter type")

    if parameter.allowed_values and value not in parameter.allowed_values:
        raise ToolArgumentError(f"{parameter.name} has an unsupported value")

    return value


def _validate_number(parameter: ToolParameter, value: int | float) -> None:
    if parameter.minimum is not None and value < parameter.minimum:
        raise ToolArgumentError(f"{parameter.name} is below its minimum")
    if parameter.maximum is not None and value > parameter.maximum:
        raise ToolArgumentError(f"{parameter.name} exceeds its maximum")


def _validate_length(parameter: ToolParameter, length: int) -> None:
    if parameter.min_length is not None and length < parameter.min_length:
        raise ToolArgumentError(f"{parameter.name} is too short")
    if parameter.max_length is not None and length > parameter.max_length:
        raise ToolArgumentError(f"{parameter.name} is too long")


def _validate_items(parameter: ToolParameter, values: list[object]) -> None:
    if parameter.min_items is not None and len(values) < parameter.min_items:
        raise ToolArgumentError(f"{parameter.name} contains too few items")
    if parameter.max_items is not None and len(values) > parameter.max_items:
        raise ToolArgumentError(f"{parameter.name} contains too many items")

    if parameter.items is None:  # Guarded by ToolParameter construction.
        raise ToolArgumentError(f"{parameter.name} has no item schema")

    for value in values:
        _validate_value(parameter.items, value)
