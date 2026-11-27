"""Network-free behavioral tests for the central orchestration workflow."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from kosmos.core.exceptions import (
    ContextLimitExceededError,
    InferenceError,
    InvalidProviderResponseError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SessionBusyError,
    ToolCapabilityUnavailableError,
)
from kosmos.core.orchestration import (
    CoreOrchestrator,
    EffortLevel,
    EffortPolicy,
    OrchestrationContextPolicy,
    OrchestrationStatus,
)
from kosmos.intelligence.conversation import ContextPolicy
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
    MessageRole,
)
from kosmos.intelligence.personality import (
    KOSMOS_INSTITUTIONAL_KNOWLEDGE,
    PersonalityEngine,
    PersonalityProfile,
)
from kosmos.intelligence.tools import (
    ToolAuthorization,
    ToolCall,
    ToolDefinition,
    ToolInferenceRequest,
    ToolInferenceResponse,
    ToolRegistry,
    ToolResultStatus,
    create_builtin_registry,
)


@dataclass(slots=True)
class ScriptedProvider:
    text_responses: list[InferenceResponse | Exception] = field(default_factory=list)
    tool_responses: list[ToolInferenceResponse | Exception] = field(default_factory=list)
    chunks: tuple[InferenceChunk, ...] = ()
    text_requests: list[InferenceRequest] = field(default_factory=list)
    tool_requests: list[ToolInferenceRequest] = field(default_factory=list)

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.text_requests.append(request)
        response = self.text_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def generate_with_tools(self, request: ToolInferenceRequest) -> ToolInferenceResponse:
        self.tool_requests.append(request)
        response = self.tool_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.text_requests.append(request)

        for chunk in self.chunks:
            yield chunk


def test_default_low_direct_response_uses_text_inference_and_commits_turn() -> None:
    provider = ScriptedProvider(text_responses=[InferenceResponse("test-model", "Olá, senhor.")])
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    result = asyncio.run(orchestrator.generate(session.session_id, "Olá.", model="test-model"))
    confirmed = orchestrator.get_session(session.session_id)

    assert result.status is OrchestrationStatus.COMPLETED
    assert result.effort is EffortLevel.LOW
    assert result.content == "Olá, senhor."
    assert result.metrics.inferences_started == 1
    assert provider.text_requests[0].thinking is False
    assert KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction() in (
        provider.text_requests[0].messages[0].content
    )
    assert "No structured tools are available for this turn." in (
        provider.text_requests[0].messages[0].content
    )
    assert "Operational tool guidance" not in session.system_instruction
    assert [message.role for message in confirmed.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert confirmed.is_busy is False


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            InvalidProviderResponseError("invalid"),
            OrchestrationStatus.INVALID_RESPONSE,
        ),
        (
            ProviderUnavailableError("unavailable"),
            OrchestrationStatus.PROVIDER_UNAVAILABLE,
        ),
        (ProviderTimeoutError("timeout"), OrchestrationStatus.PROVIDER_TIMEOUT),
        (
            ProviderHTTPError("http failure", 500),
            OrchestrationStatus.PROVIDER_HTTP_ERROR,
        ),
        (InferenceError("inference failure"), OrchestrationStatus.INFERENCE_ERROR),
    ],
)
def test_specific_inference_failures_map_to_their_controlled_status(
    error: Exception,
    expected_status: OrchestrationStatus,
) -> None:
    orchestrator = CoreOrchestrator(ScriptedProvider(text_responses=[error]))
    session = orchestrator.create_session()

    result = asyncio.run(orchestrator.generate(session.session_id, "request", model="test-model"))

    assert result.status is expected_status
    assert result.metrics.inferences_started == 1
    assert result.metrics.inferences_completed == 0
    assert orchestrator.get_session(session.session_id).messages == ()


def test_turn_guidance_reflects_effective_tools_without_persisting_across_efforts() -> None:
    provider = ScriptedProvider(
        text_responses=[InferenceResponse("test-model", "instant")],
        tool_responses=[ToolInferenceResponse("test-model", "low", ())],
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()
    authorization = ToolAuthorization(("calculate", "count_items"))

    instant = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "first",
            model="test-model",
            effort=EffortLevel.INSTANT,
            authorization=authorization,
            selected_tools=("calculate", "count_items"),
        )
    )
    low = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "second",
            model="test-model",
            effort=EffortLevel.LOW,
            authorization=authorization,
            selected_tools=("calculate", "count_items"),
        )
    )

    instant_instruction = provider.text_requests[0].messages[0].content
    low_instruction = provider.tool_requests[0].messages[0].content
    assert instant.status is OrchestrationStatus.COMPLETED
    assert low.status is OrchestrationStatus.COMPLETED
    assert "disabled by the current effort policy" in instant_instruction
    assert "Available and authorized tools: calculate, count_items." in low_instruction
    assert "prefer a tool call over mental computation" in low_instruction
    assert "disabled by the current effort policy" not in low_instruction
    assert (
        "Operational tool guidance"
        not in orchestrator.get_session(session.session_id).system_instruction
    )


@pytest.mark.parametrize(
    ("effort", "thinking"),
    [(EffortLevel.LOW, False), (EffortLevel.MEDIUM, True), (EffortLevel.HIGH, True)],
)
def test_tool_guidance_preserves_enabled_effort_policies(
    effort: EffortLevel,
    thinking: bool,
) -> None:
    provider = ScriptedProvider(tool_responses=[ToolInferenceResponse("test-model", "done", ())])
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "request",
            model="test-model",
            effort=effort,
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    request = provider.tool_requests[0]
    assert result.status is OrchestrationStatus.COMPLETED
    assert request.thinking is thinking
    assert request.tools[0].name == "calculate"
    assert "Available and authorized tools: calculate." in request.messages[0].content
    assert result.metrics.context.requests[0].serialized_request_characters > sum(
        len(message.content) for message in request.messages
    )


def test_context_metrics_measure_selection_without_exposing_message_content() -> None:
    provider = ScriptedProvider(text_responses=[InferenceResponse("test-model", "done")])
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(session.session_id, "private value", model="test-model")
    )
    context = result.metrics.context

    assert context.conversation is not None
    assert context.conversation.total_confirmed_turns == 0
    assert context.conversation.character_budget == 8_000
    assert context.requests[0].request_kind == "text"
    assert context.requests[0].response_reserve_characters == 2_000
    assert context.requests[0].serialized_request_characters <= 10_000
    assert "private value" not in repr(context)
    with pytest.raises(FrozenInstanceError):
        context.requests[0].omitted_history_turns = 1  # type: ignore[misc]


def test_long_response_remains_confirmed_but_can_remove_its_turn_from_next_context() -> None:
    provider = ScriptedProvider(
        text_responses=[
            InferenceResponse("test-model", "a" * 1_500),
            InferenceResponse("test-model", "still usable"),
        ]
    )
    orchestrator = CoreOrchestrator(
        provider,
        context_policy=ContextPolicy(max_context_characters=4_000),
    )
    session = orchestrator.create_session()

    asyncio.run(orchestrator.generate(session.session_id, "first", model="test-model"))
    result = asyncio.run(orchestrator.generate(session.session_id, "second", model="test-model"))
    confirmed = orchestrator.get_session(session.session_id)

    assert len(confirmed.messages) == 4
    assert confirmed.messages[1].content == "a" * 1_500
    assert len(provider.text_requests[1].messages) == 2
    assert result.metrics.context.conversation is not None
    assert result.metrics.context.conversation.omitted_by_character_limit == 1


def test_complete_and_streaming_apply_the_same_integrated_history_reduction() -> None:
    complete_provider = ScriptedProvider(
        text_responses=[
            *(InferenceResponse("test-model", "a" * 500) for _ in range(4)),
            InferenceResponse("test-model", "complete"),
        ]
    )
    stream_provider = ScriptedProvider(
        text_responses=[InferenceResponse("test-model", "a" * 500) for _ in range(4)],
        chunks=(InferenceChunk("test-model", "streamed", done=True),),
    )
    conversation_policy = ContextPolicy(max_context_characters=20_000)
    integrated_policy = OrchestrationContextPolicy(5_000, 500)
    complete = CoreOrchestrator(
        complete_provider,
        context_policy=conversation_policy,
        orchestration_context_policy=integrated_policy,
    )
    streaming = CoreOrchestrator(
        stream_provider,
        context_policy=conversation_policy,
        orchestration_context_policy=integrated_policy,
    )
    complete_session = complete.create_session()
    stream_session = streaming.create_session()

    for turn in range(4):
        message = f"turn-{turn}:" + "u" * 493
        asyncio.run(complete.generate(complete_session.session_id, message, model="test-model"))
        asyncio.run(streaming.generate(stream_session.session_id, message, model="test-model"))

    complete_result = asyncio.run(
        complete.generate(
            complete_session.session_id,
            "current",
            model="test-model",
            effort=EffortLevel.INSTANT,
        )
    )

    async def consume_stream() -> None:
        stream = streaming.stream(
            stream_session.session_id,
            "current",
            model="test-model",
            effort=EffortLevel.INSTANT,
        )
        assert stream.context_metrics.conversation is not None
        assert stream.context_metrics.conversation.selected_history_turns == 4
        assert stream.context_metrics.requests[0].omitted_history_turns == 3
        async for _ in stream:
            pass

    asyncio.run(consume_stream())

    complete_request = complete_provider.text_requests[-1]
    stream_request = stream_provider.text_requests[-1]
    assert complete_request.messages == stream_request.messages
    assert complete_result.metrics.context.requests[0].omitted_history_turns == 3
    assert complete_result.metrics.context.requests[0].context_limit_reached is True


def test_tool_context_rejects_known_oversized_proposal_before_execution() -> None:
    call = ToolCall("call_1", "count_items", {"items": ["x" * 200] * 20})
    provider = ScriptedProvider(tool_responses=[ToolInferenceResponse("test-model", "", (call,))])
    orchestrator = CoreOrchestrator(
        provider,
        tool_registry=create_builtin_registry(),
        orchestration_context_policy=OrchestrationContextPolicy(5_000, 500),
    )
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "count",
            model="test-model",
            authorization=ToolAuthorization(("count_items",)),
            selected_tools=("count_items",),
        )
    )

    request_metrics = result.metrics.context.requests[0]
    assert result.status is OrchestrationStatus.CONTEXT_LIMIT
    assert result.metrics.handlers_invoked == 0
    assert result.tool_results == ()
    assert (
        request_metrics.serialized_request_characters > request_metrics.selected_message_characters
    )
    assert len(provider.tool_requests) == 1
    assert orchestrator.get_session(session.session_id).messages == ()


def test_known_batch_context_exhaustion_stops_before_the_next_tool_execution() -> None:
    invocations = 0

    def large_result(_: object) -> dict[str, str]:
        nonlocal invocations
        invocations += 1
        return {"payload": "x" * 2_000}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition("large_result", "Return a large test result.", ()),
        large_result,
    )
    calls = (
        ToolCall("call_1", "large_result", {}),
        ToolCall("call_2", "large_result", {}),
    )
    provider = ScriptedProvider(tool_responses=[ToolInferenceResponse("test-model", "", calls)])
    orchestrator = CoreOrchestrator(
        provider,
        tool_registry=registry,
        orchestration_context_policy=OrchestrationContextPolicy(5_000, 500),
    )
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "run",
            model="test-model",
            authorization=ToolAuthorization(("large_result",)),
            selected_tools=("large_result",),
        )
    )

    assert result.status is OrchestrationStatus.CONTEXT_LIMIT
    assert result.metrics.tool_proposals == 2
    assert result.metrics.handlers_invoked == 1
    assert len(result.tool_results) == 1
    assert invocations == 1


def test_provider_metric_indices_preserve_missing_optional_values() -> None:
    call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 2})
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", (call,)),
            ToolInferenceResponse(
                "test-model",
                "Three.",
                (),
                InferenceMetrics(eval_count=7),
            ),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "add",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert result.metrics.inference_metric_indices == (2,)
    assert result.metrics.inference_metrics[0].eval_count == 7


def test_calculate_flow_executes_and_continues_with_structured_result() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "Vou calcular.", (call,)),
            ToolInferenceResponse("test-model", "O resultado é 4.000, senhor.", ()),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Quanto é 125 multiplicado por 32?",
            model="test-model",
            effort=EffortLevel.LOW,
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert result.content == "O resultado é 4.000, senhor."
    assert result.tool_results[0].data == {"result": 4_000}
    assert result.metrics.inferences_started == 2
    assert result.metrics.tool_proposals == 1
    assert result.metrics.handlers_invoked == 1
    assert result.metrics.tools_succeeded == 1
    assert provider.tool_requests[0].tools[0].name == "calculate"
    assert KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction() in (
        provider.tool_requests[0].messages[0].content
    )
    assert "prefer a tool call over mental computation" in (
        provider.tool_requests[0].messages[0].content
    )
    continuation = provider.tool_requests[1].messages
    assert continuation[-2].tool_calls == (call,)
    assert '"result":4000' in continuation[-1].content


def test_dependent_calculations_use_confirmed_results_across_inferences() -> None:
    first = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 25, "b": 4},
    )
    second = ToolCall(
        "call_2",
        "calculate",
        {"operation": "add", "a": 100, "b": 35},
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", (first,)),
            ToolInferenceResponse("test-model", "", (second,)),
            ToolInferenceResponse("test-model", "135, senhor.", ()),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Multiplique 25 por 4 e depois some 35.",
            model="test-model",
            effort=EffortLevel.LOW,
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert [item.data for item in result.tool_results] == [{"result": 100}, {"result": 135}]
    assert result.tool_calls == (first, second)
    assert '"result":100' in provider.tool_requests[1].messages[-1].content
    assert '"result":135' in provider.tool_requests[2].messages[-1].content


def test_proposed_division_by_zero_preserves_failure_evidence() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "divide", "a": 100, "b": 0},
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", (call,)),
            ToolInferenceResponse("test-model", "Essa divisão é indefinida, senhor.", ()),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Divida 100 por zero.",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert result.tool_calls == (call,)
    assert result.tool_results[0].status is ToolResultStatus.EXECUTION_FAILED
    assert result.metrics.handlers_invoked == 1
    assert result.metrics.tools_succeeded == 0
    assert result.metrics.tools_rejected_or_failed == 1
    assert result.content == "Essa divisão é indefinida, senhor."


def test_provider_timeout_after_execution_preserves_tool_evidence() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", (call,)),
            ProviderTimeoutError("provider timed out"),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Calcule.",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.PROVIDER_TIMEOUT
    assert result.tool_calls == (call,)
    assert result.tool_results[0].status is ToolResultStatus.SUCCESS
    assert result.metrics.inferences_started == 2
    assert result.metrics.inferences_completed == 1
    assert orchestrator.get_session(session.session_id).messages == ()


def test_multiple_tools_execute_sequentially_in_proposal_order() -> None:
    calls = (
        ToolCall("call_1", "count_items", {"items": ["one", "two", "three"]}),
        ToolCall("call_2", "calculate", {"operation": "add", "a": 2, "b": 3}),
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", calls),
            ToolInferenceResponse("test-model", "Concluído.", ()),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Conte e some.",
            model="test-model",
            authorization=ToolAuthorization(("count_items", "calculate")),
            selected_tools=("calculate", "count_items"),
        )
    )

    assert [item.call_id for item in result.tool_results] == ["call_1", "call_2"]
    assert [item.status for item in result.tool_results] == [
        ToolResultStatus.SUCCESS,
        ToolResultStatus.SUCCESS,
    ]
    assert [tool.name for tool in provider.tool_requests[0].tools] == [
        "calculate",
        "count_items",
    ]


def test_unauthorized_or_unselected_tools_are_not_advertised() -> None:
    provider = ScriptedProvider(text_responses=[InferenceResponse("test-model", "Negado.")])
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Use calculate.",
            model="test-model",
            authorization=ToolAuthorization(("count_items",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert provider.tool_requests == []
    assert len(provider.text_requests) == 1


def test_tool_batch_over_budget_is_rejected_before_any_execution() -> None:
    calls = (
        ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 1}),
        ToolCall("call_2", "calculate", {"operation": "add", "a": 2, "b": 2}),
        ToolCall("call_3", "calculate", {"operation": "add", "a": 3, "b": 3}),
    )
    provider = ScriptedProvider(tool_responses=[ToolInferenceResponse("test-model", "", calls)])
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Faça três cálculos.",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.TOOL_LIMIT
    assert result.metrics.tool_proposals == 3
    assert result.metrics.handlers_invoked == 0
    assert result.tool_results == ()
    assert orchestrator.get_session(session.session_id).messages == ()


def test_model_cannot_expand_effective_tool_authorization() -> None:
    unauthorized_call = ToolCall(
        "call_1",
        "count_items",
        {"items": ["one", "two"]},
    )
    provider = ScriptedProvider(
        tool_responses=[
            ToolInferenceResponse("test-model", "", (unauthorized_call,)),
            ToolInferenceResponse("test-model", "A operação foi negada.", ()),
        ]
    )
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Calcule um valor.",
            model="test-model",
            authorization=ToolAuthorization(("calculate", "count_items")),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert result.tool_results[0].status is ToolResultStatus.UNAUTHORIZED
    assert result.metrics.handlers_invoked == 0
    assert result.metrics.tools_rejected_or_failed == 1
    assert [tool.name for tool in provider.tool_requests[0].tools] == ["calculate"]


def test_last_inference_tool_calls_are_not_executed() -> None:
    policy = EffortPolicy(EffortLevel.LOW, False, True, 1, 2, 60)
    call = ToolCall("call_1", "calculate", {"operation": "add", "a": 1, "b": 1})
    provider = ScriptedProvider(tool_responses=[ToolInferenceResponse("test-model", "", (call,))])
    orchestrator = CoreOrchestrator(
        provider,
        tool_registry=create_builtin_registry(),
        effort_policies={EffortLevel.LOW: policy},
    )
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(
            session.session_id,
            "Calcule.",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )
    )

    assert result.status is OrchestrationStatus.INFERENCE_LIMIT
    assert result.metrics.handlers_invoked == 0


def test_provider_without_tool_capability_fails_explicitly() -> None:
    @dataclass
    class TextOnlyProvider:
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            return InferenceResponse(request.model, "text")

        async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
            if False:
                yield InferenceChunk(request.model, "")

    orchestrator = CoreOrchestrator(TextOnlyProvider(), tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    with pytest.raises(ToolCapabilityUnavailableError):
        asyncio.run(
            orchestrator.generate(
                session.session_id,
                "Calcule.",
                model="test-model",
                authorization=ToolAuthorization(("calculate",)),
                selected_tools=("calculate",),
            )
        )


def test_required_context_over_budget_returns_controlled_result() -> None:
    provider = ScriptedProvider(text_responses=[InferenceResponse("test-model", "unused")])
    orchestrator = CoreOrchestrator(
        provider,
        orchestration_context_policy=OrchestrationContextPolicy(100, 10),
    )
    session = orchestrator.create_session()

    result = asyncio.run(orchestrator.generate(session.session_id, "request", model="test-model"))

    assert result.status is OrchestrationStatus.CONTEXT_LIMIT
    assert provider.text_requests == []
    assert orchestrator.get_session(session.session_id).messages == ()
    assert result.metrics.context.conversation is not None
    assert result.metrics.context.requests == ()


def test_stream_preserves_chunks_and_commits_only_on_completion() -> None:
    provider = ScriptedProvider(
        chunks=(
            InferenceChunk("test-model", "Olá, "),
            InferenceChunk("test-model", "senhor.", done=True),
        )
    )
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    async def consume() -> list[str]:
        stream = orchestrator.stream(
            session.session_id,
            "Olá.",
            model="test-model",
            effort=EffortLevel.INSTANT,
        )
        return [chunk.content async for chunk in stream]

    chunks = asyncio.run(consume())

    assert chunks == ["Olá, ", "senhor."]
    assert KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction() in (
        provider.text_requests[0].messages[0].content
    )
    assert orchestrator.get_session(session.session_id).messages[-1].content == "Olá, senhor."


def test_institutional_instruction_survives_clear_without_personal_user_memory() -> None:
    provider = ScriptedProvider(
        text_responses=[
            InferenceResponse("test-model", "first"),
            InferenceResponse("test-model", "second"),
        ]
    )
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    asyncio.run(orchestrator.generate(session.session_id, "Meu nome é André", model="test-model"))
    cleared = orchestrator.clear_session(session.session_id)
    asyncio.run(orchestrator.generate(session.session_id, "Quem criou você?", model="test-model"))

    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()
    assert cleared.messages == ()
    assert knowledge in cleared.system_instruction
    request_instruction = provider.text_requests[1].messages[0].content
    assert request_instruction.startswith(cleared.system_instruction)
    assert "No structured tools are available for this turn." in request_instruction
    assert "Operational tool guidance" not in cleared.system_instruction
    second_request = provider.text_requests[1]
    assert all("André" not in message.content for message in second_request.messages)


@pytest.mark.parametrize(
    "effort",
    [EffortLevel.INSTANT, EffortLevel.LOW, EffortLevel.MEDIUM, EffortLevel.HIGH],
)
def test_institutional_instruction_is_available_at_every_supported_effort(
    effort: EffortLevel,
) -> None:
    provider = ScriptedProvider(text_responses=[InferenceResponse("test-model", "done")])
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    result = asyncio.run(
        orchestrator.generate(session.session_id, "request", model="test-model", effort=effort)
    )

    assert result.status is OrchestrationStatus.COMPLETED
    assert KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction() in (
        provider.text_requests[0].messages[0].content
    )


def test_custom_personalities_keep_shared_knowledge_and_session_isolation() -> None:
    provider = ScriptedProvider(
        text_responses=[
            InferenceResponse("test-model", "formal"),
            InferenceResponse("test-model", "relaxed"),
        ]
    )
    formal = CoreOrchestrator(
        provider,
        personality=PersonalityEngine(PersonalityProfile(formality=100)),
    )
    relaxed = CoreOrchestrator(
        provider,
        personality=PersonalityEngine(PersonalityProfile(formality=0)),
    )
    formal_session = formal.create_session()
    relaxed_session = relaxed.create_session()

    asyncio.run(formal.generate(formal_session.session_id, "one", model="test-model"))
    asyncio.run(relaxed.generate(relaxed_session.session_id, "two", model="test-model"))

    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()
    formal_instruction = provider.text_requests[0].messages[0].content
    relaxed_instruction = provider.text_requests[1].messages[0].content
    assert formal_instruction != relaxed_instruction
    assert knowledge in formal_instruction
    assert knowledge in relaxed_instruction
    assert formal.get_session(formal_session.session_id).messages[0].content == "one"
    assert relaxed.get_session(relaxed_session.session_id).messages[0].content == "two"


def test_stream_rejects_integrated_context_before_provider_inference() -> None:
    provider = ScriptedProvider(chunks=(InferenceChunk("test-model", "unused", done=True),))
    orchestrator = CoreOrchestrator(
        provider,
        orchestration_context_policy=OrchestrationContextPolicy(100, 10),
    )
    session = orchestrator.create_session()

    with pytest.raises(ContextLimitExceededError):
        orchestrator.stream(
            session.session_id,
            "x" * 100,
            model="test-model",
            effort=EffortLevel.INSTANT,
        )

    assert provider.text_requests == []
    assert orchestrator.get_session(session.session_id).is_busy is False


def test_stream_rejects_selected_authorized_tools() -> None:
    provider = ScriptedProvider(chunks=(InferenceChunk("test-model", "done", done=True),))
    orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
    session = orchestrator.create_session()

    with pytest.raises(ValueError, match="cannot be combined"):
        orchestrator.stream(
            session.session_id,
            "Calcule.",
            model="test-model",
            authorization=ToolAuthorization(("calculate",)),
            selected_tools=("calculate",),
        )


def test_session_remains_busy_during_coordinated_provider_wait() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    @dataclass(slots=True)
    class BlockingProvider(ScriptedProvider):
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            started.set()
            await release.wait()
            return InferenceResponse(request.model, "done")

    provider = BlockingProvider()
    orchestrator = CoreOrchestrator(provider)
    session = orchestrator.create_session()

    async def scenario() -> None:
        task = asyncio.create_task(
            orchestrator.generate(session.session_id, "wait", model="test-model")
        )
        await started.wait()

        with pytest.raises(SessionBusyError):
            orchestrator.clear_session(session.session_id)

        release.set()
        await task

    asyncio.run(scenario())


def test_external_cancellation_releases_session_without_committing() -> None:
    started = asyncio.Event()

    @dataclass(slots=True)
    class NeverCompletesProvider(ScriptedProvider):
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    orchestrator = CoreOrchestrator(NeverCompletesProvider())
    session = orchestrator.create_session()

    async def scenario() -> None:
        task = asyncio.create_task(
            orchestrator.generate(session.session_id, "cancel", model="test-model")
        )
        await started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    snapshot = orchestrator.get_session(session.session_id)
    assert snapshot.is_busy is False
    assert snapshot.messages == ()


def test_total_timeout_releases_session_without_committing() -> None:
    @dataclass(slots=True)
    class NeverCompletesProvider(ScriptedProvider):
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    policy = EffortPolicy(EffortLevel.LOW, False, True, 3, 2, 0.01)
    orchestrator = CoreOrchestrator(
        NeverCompletesProvider(),
        effort_policies={EffortLevel.LOW: policy},
    )
    session = orchestrator.create_session()

    result = asyncio.run(orchestrator.generate(session.session_id, "timeout", model="test-model"))
    snapshot = orchestrator.get_session(session.session_id)

    assert result.status is OrchestrationStatus.TIMEOUT
    assert result.metrics.inferences_started == 1
    assert result.metrics.inferences_completed == 0
    assert snapshot.is_busy is False
    assert snapshot.messages == ()
