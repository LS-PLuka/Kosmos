"""Minimal deny-by-default authorization for Stage 01.5 pure tools."""

from collections.abc import Iterable
from dataclasses import dataclass

from kosmos.intelligence.tools.models import ToolDefinition, ToolRisk


@dataclass(frozen=True, slots=True)
class ToolAuthorization:
    """An explicit execution-scoped allowlist supplied by trusted application code."""

    allowed_tools: frozenset[str] = frozenset()

    def __init__(self, allowed_tools: Iterable[str] = ()) -> None:
        names = frozenset(allowed_tools)

        if not all(isinstance(name, str) and name for name in names):
            raise TypeError("allowed tool names must be non-empty strings")

        object.__setattr__(self, "allowed_tools", names)

    def permits(self, definition: ToolDefinition) -> bool:
        """Permit only explicitly allowed PURE tools in this stage."""

        return definition.risk is ToolRisk.PURE and definition.name in self.allowed_tools
