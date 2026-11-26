"""Network-free manual composition of the Stage 01.5 tool-calling flow."""

import asyncio
from dataclasses import dataclass, field

from kosmos.intelligence.tools import (
    CALCULATE_DEFINITION,
    ToolAuthorization,
    ToolCall,
    ToolExecutor,
    ToolInferenceRequest,
    ToolInferenceResponse,
    ToolMessage,
    ToolMessageRole,
    ToolResultStatus,
    create_builtin_registry,
)


@dataclass(slots=True)
class FakeToolProvider:
    responses: list[ToolInferenceResponse]
    requests: list[ToolInferenceRequest] = field(default_factory=list)

    async def generate_with_tools(self, request: ToolInferenceRequest) -> ToolInferenceResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def test_explicit_call_execution_and_continuation_flow() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    provider = FakeToolProvider(
        [
            ToolInferenceResponse("qwen-test", "", (call,)),
            ToolInferenceResponse("qwen-test", "The result is 4000.", ()),
        ]
    )
    first_request = ToolInferenceRequest(
        "qwen-test",
        (ToolMessage(ToolMessageRole.USER, "Multiply 125 by 32."),),
        (CALCULATE_DEFINITION,),
    )

    first_response = asyncio.run(provider.generate_with_tools(first_request))
    result = asyncio.run(
        ToolExecutor(create_builtin_registry()).execute(
            first_response.tool_calls[0],
            ToolAuthorization(("calculate",)),
        )
    )
    continuation = ToolInferenceRequest(
        "qwen-test",
        (
            first_request.messages[0],
            first_response.as_message(),
            ToolMessage.from_result(result),
        ),
        (CALCULATE_DEFINITION,),
    )
    final_response = asyncio.run(provider.generate_with_tools(continuation))

    assert result.status is ToolResultStatus.SUCCESS
    assert result.data == {"result": 4_000}
    assert final_response.content == "The result is 4000."
    assert len(provider.requests) == 2


def test_denied_flow_never_invokes_handler() -> None:
    calls = 0
    registry = create_builtin_registry()
    registered = registry.get("calculate")

    def tracked_handler(arguments):
        nonlocal calls
        calls += 1
        return registered.handler(arguments)

    replacement_registry = type(registry)()
    replacement_registry.register(CALCULATE_DEFINITION, tracked_handler)
    call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})

    result = asyncio.run(ToolExecutor(replacement_registry).execute(call, ToolAuthorization()))

    assert result.status is ToolResultStatus.UNAUTHORIZED
    assert calls == 0
