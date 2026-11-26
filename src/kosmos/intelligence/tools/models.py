"""Provider-independent contracts for structured tool calling."""

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from kosmos.intelligence.models import InferenceMetrics

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]
type FrozenJSON = JSONScalar | tuple[FrozenJSON, ...] | Mapping[str, FrozenJSON]

_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class ParameterType(str, Enum):
    """Supported parameter types in the Stage 01.5 schema subset."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"


class ToolRisk(str, Enum):
    """Trusted execution-risk classification."""

    PURE = "pure"
    READ_ONLY = "read_only"
    SIDE_EFFECT = "side_effect"
    SENSITIVE = "sensitive"


class ToolResultStatus(str, Enum):
    """Stable outcomes produced by the tool executor."""

    SUCCESS = "success"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    UNAUTHORIZED = "unauthorized"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class ToolParameter:
    """One validated parameter and its model-visible schema constraints."""

    name: str
    type: ParameterType
    description: str
    required: bool = True
    allowed_values: tuple[JSONScalar, ...] = ()
    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_items: int | None = None
    max_items: int | None = None
    items: "ToolParameter | None" = None

    def __post_init__(self) -> None:
        _validate_name(self.name, "parameter name")
        _validate_text(self.description, "parameter description")

        if not isinstance(self.type, ParameterType):
            raise TypeError("parameter type must be a ParameterType")

        if not isinstance(self.required, bool):
            raise TypeError("parameter required must be a boolean")

        allowed_values = tuple(self.allowed_values)
        object.__setattr__(self, "allowed_values", allowed_values)

        _validate_parameter_constraints(self)

    def to_schema(self) -> dict[str, JSONValue]:
        """Return the exact compact JSON Schema subset advertised to providers."""

        schema: dict[str, JSONValue] = {"type": self.type.value, "description": self.description}

        if self.allowed_values:
            schema["enum"] = list(self.allowed_values)
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        if self.maximum is not None:
            schema["maximum"] = self.maximum
        if self.min_length is not None:
            schema["minLength"] = self.min_length
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
        if self.min_items is not None:
            schema["minItems"] = self.min_items
        if self.max_items is not None:
            schema["maxItems"] = self.max_items
        if self.items is not None:
            schema["items"] = self.items.to_schema()

        return schema


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Trusted public metadata for one explicitly registered tool."""

    name: str
    description: str
    parameters: tuple[ToolParameter, ...]
    risk: ToolRisk = ToolRisk.PURE

    def __post_init__(self) -> None:
        _validate_name(self.name, "tool name")
        _validate_text(self.description, "tool description")

        if not isinstance(self.parameters, Sequence) or isinstance(self.parameters, str | bytes):
            raise TypeError("parameters must be a sequence of ToolParameter instances")

        parameters = tuple(self.parameters)

        if not all(isinstance(parameter, ToolParameter) for parameter in parameters):
            raise TypeError("parameters must contain only ToolParameter instances")

        names = [parameter.name for parameter in parameters]

        if len(names) != len(set(names)):
            raise ValueError("tool parameter names must be unique")

        if not isinstance(self.risk, ToolRisk):
            raise TypeError("tool risk must be a ToolRisk")

        object.__setattr__(self, "parameters", parameters)

    def to_provider_schema(self) -> dict[str, JSONValue]:
        """Return public metadata without handlers or authorization internals."""

        properties = {parameter.name: parameter.to_schema() for parameter in self.parameters}
        required = [parameter.name for parameter in self.parameters if parameter.required]

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    """An untrusted provider proposal correlated by a local identifier."""

    call_id: str
    name: str
    arguments: Mapping[str, FrozenJSON]

    def __post_init__(self) -> None:
        _validate_text(self.call_id, "tool call id")
        _validate_name(self.name, "tool call name")

        if not isinstance(self.arguments, Mapping):
            raise TypeError("tool call arguments must be an object")

        frozen = _freeze_json(dict(self.arguments))

        if not isinstance(frozen, Mapping):
            raise TypeError("tool call arguments must be an object")

        object.__setattr__(self, "arguments", frozen)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A safe structured result correlated with a proposed call."""

    call_id: str
    tool_name: str
    status: ToolResultStatus
    data: FrozenJSON = None
    error_code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        _validate_text(self.call_id, "tool result call id")
        _validate_name(self.tool_name, "tool result name")

        if not isinstance(self.status, ToolResultStatus):
            raise TypeError("tool result status must be a ToolResultStatus")

        if self.error_code is not None:
            _validate_name(self.error_code, "tool result error code")

        if self.message is not None:
            _validate_text(self.message, "tool result message")

        object.__setattr__(self, "data", _freeze_json(self.data))

    def to_payload(self) -> dict[str, JSONValue]:
        """Return the bounded model-facing result payload."""

        payload: dict[str, JSONValue] = {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "data": thaw_json(self.data),
        }

        if self.error_code is not None:
            payload["error_code"] = self.error_code
        if self.message is not None:
            payload["message"] = self.message

        return payload


class ToolMessageRole(str, Enum):
    """Roles supported by provider-independent tool conversations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ToolMessage:
    """One structured message used only by explicit tool inference flows."""

    role: ToolMessageRole
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, ToolMessageRole):
            raise TypeError("tool message role must be a ToolMessageRole")

        if not isinstance(self.content, str):
            raise TypeError("tool message content must be a string")

        calls = tuple(self.tool_calls)

        if not all(isinstance(call, ToolCall) for call in calls):
            raise TypeError("tool_calls must contain only ToolCall instances")

        if self.tool_name is not None:
            _validate_name(self.tool_name, "tool message tool name")

        if self.role is ToolMessageRole.TOOL and self.tool_name is None:
            raise ValueError("tool messages require a tool name")

        if self.role is not ToolMessageRole.TOOL and self.tool_name is not None:
            raise ValueError("only tool messages may include a tool name")

        if self.role is not ToolMessageRole.ASSISTANT and calls:
            raise ValueError("only assistant messages may include tool calls")

        if not self.content.strip() and not calls:
            raise ValueError("tool message must contain text or tool calls")

        object.__setattr__(self, "tool_calls", calls)

    @classmethod
    def from_result(cls, result: ToolResult) -> "ToolMessage":
        """Build the Ollama-compatible tool-result message for a later inference."""

        if not isinstance(result, ToolResult):
            raise TypeError("result must be a ToolResult")

        content = json.dumps(result.to_payload(), ensure_ascii=False, separators=(",", ":"))
        return cls(ToolMessageRole.TOOL, content, tool_name=result.tool_name)


@dataclass(frozen=True, slots=True)
class ToolInferenceRequest:
    """An explicit non-streaming request with selected tool definitions."""

    model: str
    messages: tuple[ToolMessage, ...]
    tools: tuple[ToolDefinition, ...]
    thinking: bool | None = None

    def __post_init__(self) -> None:
        _validate_text(self.model, "model")
        messages = tuple(self.messages)
        tools = tuple(self.tools)

        if not messages or not all(isinstance(message, ToolMessage) for message in messages):
            raise ValueError("messages must contain at least one ToolMessage")

        if not all(isinstance(tool, ToolDefinition) for tool in tools):
            raise TypeError("tools must contain only ToolDefinition instances")

        names = [tool.name for tool in tools]

        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")

        if self.thinking is not None and not isinstance(self.thinking, bool):
            raise TypeError("thinking must be a boolean or None")

        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "tools", tools)


@dataclass(frozen=True, slots=True)
class ToolInferenceResponse:
    """A response containing text, ordered calls, or both."""

    model: str
    content: str
    tool_calls: tuple[ToolCall, ...]
    metrics: InferenceMetrics | None = None

    def __post_init__(self) -> None:
        _validate_text(self.model, "model")

        if not isinstance(self.content, str):
            raise TypeError("tool inference content must be a string")

        calls = tuple(self.tool_calls)

        if not all(isinstance(call, ToolCall) for call in calls):
            raise TypeError("tool_calls must contain only ToolCall instances")

        if not self.content.strip() and not calls:
            raise ValueError("tool inference response must contain text or tool calls")

        identifiers = [call.call_id for call in calls]

        if len(identifiers) != len(set(identifiers)):
            raise ValueError("tool call identifiers must be unique")

        if self.metrics is not None and not isinstance(self.metrics, InferenceMetrics):
            raise TypeError("metrics must be InferenceMetrics or None")

        object.__setattr__(self, "tool_calls", calls)

    def as_message(self) -> ToolMessage:
        """Represent this response for an explicitly requested continuation."""

        return ToolMessage(ToolMessageRole.ASSISTANT, self.content, self.tool_calls)


def thaw_json(value: FrozenJSON) -> JSONValue:
    """Return a detached mutable JSON representation."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}

    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]

    return value


def _freeze_json(value: object, *, depth: int = 0) -> FrozenJSON:
    if depth > 8:
        raise ValueError("JSON value exceeds the maximum depth of 8")

    if value is None or isinstance(value, str | bool | int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")

        return value

    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJSON] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")

            frozen[key] = _freeze_json(item, depth=depth + 1)

        return MappingProxyType(frozen)

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_json(item, depth=depth + 1) for item in value)

    raise TypeError("value must be JSON serializable")


def _validate_parameter_constraints(parameter: ToolParameter) -> None:
    numeric = parameter.type in {ParameterType.INTEGER, ParameterType.NUMBER}
    string = parameter.type is ParameterType.STRING
    array = parameter.type is ParameterType.ARRAY

    for value in parameter.allowed_values:
        if not _matches_parameter_scalar_type(parameter.type, value):
            raise TypeError("allowed values must match the parameter type")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("allowed numeric values must be finite")

    if (parameter.minimum is not None or parameter.maximum is not None) and not numeric:
        raise ValueError("numeric limits require an integer or number parameter")

    for value in (parameter.minimum, parameter.maximum):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise TypeError("numeric limits must be numbers")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric limits must be finite")

    if (
        parameter.minimum is not None
        and parameter.maximum is not None
        and parameter.minimum > parameter.maximum
    ):
        raise ValueError("minimum must not exceed maximum")

    if (parameter.min_length is not None or parameter.max_length is not None) and not string:
        raise ValueError("length limits require a string parameter")

    if (parameter.min_items is not None or parameter.max_items is not None) and not array:
        raise ValueError("item limits require an array parameter")

    for value in (
        parameter.min_length,
        parameter.max_length,
        parameter.min_items,
        parameter.max_items,
    ):
        invalid = isinstance(value, bool) or not isinstance(value, int) or value < 0

        if value is not None and invalid:
            raise ValueError("length and item limits must be non-negative integers")

    if (
        string
        and parameter.min_length is not None
        and parameter.max_length is not None
        and parameter.min_length > parameter.max_length
    ):
        raise ValueError("minimum length must not exceed maximum length")

    if (
        array
        and parameter.min_items is not None
        and parameter.max_items is not None
        and parameter.min_items > parameter.max_items
    ):
        raise ValueError("minimum items must not exceed maximum items")

    if array != (parameter.items is not None):
        raise ValueError("array parameters require items and non-array parameters forbid items")


def _matches_parameter_scalar_type(parameter_type: ParameterType, value: object) -> bool:
    if parameter_type is ParameterType.STRING:
        return isinstance(value, str)
    if parameter_type is ParameterType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if parameter_type is ParameterType.NUMBER:
        return isinstance(value, int | float) and not isinstance(value, bool)
    if parameter_type is ParameterType.BOOLEAN:
        return isinstance(value, bool)

    return False


def _validate_name(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not _NAME_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a snake_case identifier")


def _validate_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
