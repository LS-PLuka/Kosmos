"""Tests for Ollama's native non-streaming tool-calling protocol."""

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from kosmos.core.config import ApplicationSettings
from kosmos.core.exceptions import InvalidProviderResponseError, ProviderHTTPError
from kosmos.intelligence.providers.ollama import OllamaProvider
from kosmos.intelligence.tools import (
    CALCULATE_DEFINITION,
    ToolCall,
    ToolInferenceRequest,
    ToolMessage,
    ToolMessageRole,
    ToolResult,
    ToolResultStatus,
)


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider(ApplicationSettings(), transport=httpx.MockTransport(handler))


def _request(*messages: ToolMessage) -> ToolInferenceRequest:
    return ToolInferenceRequest(
        "qwen-test",
        messages or (ToolMessage(ToolMessageRole.USER, "Multiply 125 by 32."),),
        (CALCULATE_DEFINITION,),
    )


def _document(message: dict[str, object]) -> dict[str, object]:
    return {
        "model": "qwen-test",
        "message": {"role": "assistant", **message},
        "done": True,
        "eval_count": 4,
    }


def test_serializes_native_tools_and_compact_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_document({"content": "I can calculate that."}))

    provider = _provider(handler)
    response = asyncio.run(provider.generate_with_tools(_request()))
    asyncio.run(provider.aclose())

    assert captured["stream"] is False
    assert captured["tools"] == [CALCULATE_DEFINITION.to_provider_schema()]
    assert captured["messages"] == [{"role": "user", "content": "Multiply 125 by 32."}]
    assert response.content == "I can calculate that."
    assert response.tool_calls == ()
    assert response.metrics.eval_count == 4


def test_parses_calls_only_and_preserves_multiple_call_order() -> None:
    calls = [
        {"function": {"name": "calculate", "arguments": {"operation": "add", "a": 1, "b": 2}}},
        {"function": {"name": "count_items", "arguments": {"items": ["a", "b"]}}},
    ]
    provider = _provider(
        lambda request: httpx.Response(200, json=_document({"content": "", "tool_calls": calls}))
    )

    response = asyncio.run(provider.generate_with_tools(_request()))
    asyncio.run(provider.aclose())

    assert [call.name for call in response.tool_calls] == ["calculate", "count_items"]
    assert len({call.call_id for call in response.tool_calls}) == 2
    assert response.content == ""


def test_accepts_text_and_calls_without_executing_any_handler() -> None:
    provider = _provider(
        lambda request: httpx.Response(
            200,
            json=_document(
                {
                    "content": "I will use the calculator.",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "calculate",
                                "arguments": {"operation": "multiply", "a": 125, "b": 32},
                            }
                        }
                    ],
                }
            ),
        )
    )

    response = asyncio.run(provider.generate_with_tools(_request()))
    asyncio.run(provider.aclose())

    assert response.content == "I will use the calculator."
    assert response.tool_calls[0].arguments["a"] == 125


def test_serializes_assistant_calls_and_tool_result_for_continuation() -> None:
    captured: dict[str, object] = {}
    call = ToolCall("local_1", "calculate", {"operation": "multiply", "a": 125, "b": 32})
    result = ToolResult("local_1", "calculate", ToolResultStatus.SUCCESS, {"result": 4_000})
    messages = (
        ToolMessage(ToolMessageRole.USER, "Multiply 125 by 32."),
        ToolMessage(ToolMessageRole.ASSISTANT, "", (call,)),
        ToolMessage.from_result(result),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_document({"content": "The result is 4000."}))

    provider = _provider(handler)
    response = asyncio.run(provider.generate_with_tools(_request(*messages)))
    asyncio.run(provider.aclose())

    assert captured["messages"][1]["tool_calls"] == [
        {
            "function": {
                "name": "calculate",
                "arguments": {"operation": "multiply", "a": 125, "b": 32},
            }
        }
    ]
    assert captured["messages"][2]["role"] == "tool"
    assert captured["messages"][2]["tool_name"] == "calculate"
    assert json.loads(captured["messages"][2]["content"])["data"] == {"result": 4_000}
    assert response.content == "The result is 4000."


@pytest.mark.parametrize(
    "message",
    [
        {"content": "", "tool_calls": {}},
        {"content": "", "tool_calls": ["invalid"]},
        {"content": "", "tool_calls": [{"function": {"arguments": {}}}]},
        {"content": "", "tool_calls": [{"function": {"name": "calculate"}}]},
        {
            "content": "",
            "tool_calls": [{"function": {"name": "calculate", "arguments": []}}],
        },
        {"content": ""},
    ],
)
def test_rejects_malformed_or_empty_tool_responses(message: dict[str, object]) -> None:
    provider = _provider(lambda request: httpx.Response(200, json=_document(message)))

    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(provider.generate_with_tools(_request()))

    asyncio.run(provider.aclose())


def test_tool_inference_preserves_http_errors_and_text_streaming_contract() -> None:
    provider = _provider(lambda request: httpx.Response(503))

    with pytest.raises(ProviderHTTPError):
        asyncio.run(provider.generate_with_tools(_request()))

    asyncio.run(provider.aclose())
