"""Explicit per-instance registry for trusted tool implementations."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from kosmos.intelligence.tools.models import JSONValue, ToolDefinition

ToolHandler = Callable[[Mapping[str, object]], JSONValue | Awaitable[JSONValue]]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """Internal association that is never included in provider schemas."""

    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    """Manage explicitly registered definitions and handlers without global state."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """Register one trusted association and reject replacement."""

        if not isinstance(definition, ToolDefinition):
            raise TypeError("definition must be a ToolDefinition")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if definition.name in self._tools:
            raise ValueError(f"tool {definition.name!r} is already registered")

        self._tools[definition.name] = RegisteredTool(definition, handler)

    def get(self, name: str) -> RegisteredTool | None:
        """Return the trusted association or None for an unknown name."""

        return self._tools.get(name)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """List public definitions in registration order."""

        return tuple(tool.definition for tool in self._tools.values())

    def provider_schemas(self) -> tuple[dict[str, JSONValue], ...]:
        """List detached model-visible schemas without handlers or policy."""

        return tuple(definition.to_provider_schema() for definition in self.definitions())
