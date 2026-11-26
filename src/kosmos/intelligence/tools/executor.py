"""Validated, authorized execution of explicitly registered tool handlers."""

import inspect
import json

from kosmos.intelligence.tools.authorization import ToolAuthorization
from kosmos.intelligence.tools.models import ToolCall, ToolResult, ToolResultStatus
from kosmos.intelligence.tools.registry import ToolRegistry
from kosmos.intelligence.tools.validation import ToolArgumentError, validate_arguments

MAX_RESULT_BYTES = 16_384


class ToolExecutor:
    """Execute one call sequentially; this boundary is not a sandbox."""

    def __init__(self, registry: ToolRegistry) -> None:
        if not isinstance(registry, ToolRegistry):
            raise TypeError("registry must be a ToolRegistry")

        self._registry = registry

    async def execute(
        self,
        call: ToolCall,
        authorization: ToolAuthorization,
    ) -> ToolResult:
        """Return a safe result without retries or background execution."""

        if not isinstance(call, ToolCall):
            raise TypeError("call must be a ToolCall")
        if not isinstance(authorization, ToolAuthorization):
            raise TypeError("authorization must be a ToolAuthorization")

        registered = self._registry.get(call.name)

        if registered is None:
            return _failure(call, ToolResultStatus.UNKNOWN_TOOL, "unknown_tool", "Unknown tool.")

        if not authorization.permits(registered.definition):
            return _failure(
                call,
                ToolResultStatus.UNAUTHORIZED,
                "unauthorized",
                "Tool execution is not authorized.",
            )

        try:
            arguments = validate_arguments(registered.definition, call.arguments)
        except ToolArgumentError:
            return _failure(
                call,
                ToolResultStatus.INVALID_ARGUMENTS,
                "invalid_arguments",
                "Tool arguments are invalid.",
            )

        try:
            data = registered.handler(arguments)

            if inspect.isawaitable(data):
                data = await data

            encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

            if len(encoded.encode("utf-8")) > MAX_RESULT_BYTES:
                raise ValueError("tool result exceeds the output limit")

            return ToolResult(call.call_id, call.name, ToolResultStatus.SUCCESS, data)
        except Exception as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise

            return _failure(
                call,
                ToolResultStatus.EXECUTION_FAILED,
                "execution_failed",
                "Tool execution failed.",
            )


def _failure(
    call: ToolCall,
    status: ToolResultStatus,
    error_code: str,
    message: str,
) -> ToolResult:
    return ToolResult(call.call_id, call.name, status, error_code=error_code, message=message)
