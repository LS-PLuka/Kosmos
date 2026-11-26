"""Central coordination of conversation, inference, tools, limits, and metrics."""

import asyncio
import time
from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from kosmos.core.exceptions import (
    ContextLimitExceededError,
    InvalidProviderResponseError,
    ProviderUnavailableError,
    ToolCapabilityUnavailableError,
)
from kosmos.core.orchestration.context import OrchestrationContextPolicy
from kosmos.core.orchestration.effort import (
    EffortLevel,
    EffortPolicy,
    default_effort_policies,
    resolve_effort_policy,
)
from kosmos.core.orchestration.models import (
    OrchestrationMetrics,
    OrchestrationResult,
    OrchestrationStatus,
)
from kosmos.intelligence.conversation import (
    ContextPolicy,
    ConversationEngine,
    ConversationSession,
    ConversationStream,
)
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
    Message,
)
from kosmos.intelligence.personality import KOSMOS_INSTITUTIONAL_KNOWLEDGE, PersonalityEngine
from kosmos.intelligence.providers.base import LLMProvider, ToolCallingProvider
from kosmos.intelligence.tools import (
    ToolAuthorization,
    ToolDefinition,
    ToolExecutor,
    ToolInferenceRequest,
    ToolInferenceResponse,
    ToolMessage,
    ToolMessageRole,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
)


@dataclass(slots=True)
class _MetricsState:
    inferences_started: int = 0
    inferences_completed: int = 0
    tool_proposals: int = 0
    handlers_invoked: int = 0
    tools_succeeded: int = 0
    tools_rejected_or_failed: int = 0
    inference_metrics: list[InferenceMetrics] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


class _TurnStopped(Exception):
    def __init__(self, status: OrchestrationStatus, failure: str) -> None:
        super().__init__(failure)
        self.status = status
        self.failure = failure


class OrchestrationStream(AsyncIterator[InferenceChunk]):
    """Deadline-aware wrapper around a real conversation provider stream."""

    def __init__(self, upstream: ConversationStream, deadline_seconds: float) -> None:
        self._upstream = upstream
        self._deadline = time.monotonic() + deadline_seconds

    def __aiter__(self) -> "OrchestrationStream":
        return self

    async def __anext__(self) -> InferenceChunk:
        remaining = self._deadline - time.monotonic()

        if remaining <= 0:
            await self.aclose()
            raise TimeoutError("orchestration streaming deadline exceeded")

        try:
            return await asyncio.wait_for(anext(self._upstream), timeout=remaining)
        except TimeoutError:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        """Close the underlying stream and release its reserved conversation turn."""

        await self._upstream.aclose()


class CoreOrchestrator:
    """Expose one provider-independent intelligence workflow for future interfaces."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        tool_registry: ToolRegistry | None = None,
        personality: PersonalityEngine | None = None,
        context_policy: ContextPolicy | None = None,
        orchestration_context_policy: OrchestrationContextPolicy | None = None,
        effort_policies: Mapping[EffortLevel, EffortPolicy] | None = None,
        default_effort: EffortLevel = EffortLevel.LOW,
        tool_provider: ToolCallingProvider | None = None,
    ) -> None:
        if not isinstance(default_effort, EffortLevel):
            raise TypeError("default_effort must be an EffortLevel")

        self._provider = provider
        self._registry = tool_registry or ToolRegistry()
        self._personality = personality or PersonalityEngine()
        self._conversation = ConversationEngine(provider, context_policy)
        self._context = orchestration_context_policy or OrchestrationContextPolicy()
        self._policies = self._validate_policies(effort_policies or default_effort_policies())
        self._default_effort = default_effort
        self._tool_provider = tool_provider or self._detect_tool_provider(provider)

        resolve_effort_policy(default_effort, self._policies)

    def create_session(self) -> ConversationSession:
        """Create a session with deterministic behavioral and institutional instructions."""

        personality = self._personality.build_system_instruction()
        knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()
        instruction = "\n".join((personality, knowledge))
        return self._conversation.create_session(system_instruction=instruction)

    def get_session(self, session_id: UUID) -> ConversationSession:
        """Return a read-only snapshot from the conversation source of truth."""

        return self._conversation.get_session(session_id)

    def clear_session(self, session_id: UUID) -> ConversationSession:
        """Clear an idle session through the conversation boundary."""

        return self._conversation.clear_session(session_id)

    def delete_session(self, session_id: UUID) -> None:
        """Delete an idle session through the conversation boundary."""

        self._conversation.delete_session(session_id)

    async def generate(
        self,
        session_id: UUID,
        content: str,
        *,
        model: str,
        effort: EffortLevel | None = None,
        authorization: ToolAuthorization | None = None,
        selected_tools: Iterable[str] = (),
    ) -> OrchestrationResult:
        """Coordinate one bounded turn and return measured structured evidence."""

        level = self._default_effort if effort is None else effort
        policy = resolve_effort_policy(level, self._policies)
        active_authorization = authorization or ToolAuthorization()
        tools, execution_authorization = self._select_tools(
            selected_tools,
            active_authorization,
            enabled=policy.tools_enabled,
        )

        if tools and self._tool_provider is None:
            raise ToolCapabilityUnavailableError(
                "selected tools require a provider with structured tool-calling capability"
            )

        started_at = time.monotonic()
        state = _MetricsState()

        async def operation(messages: tuple[Message, ...]) -> str:
            if not tools:
                return await self._generate_text(messages, model, policy, state)

            return await self._generate_with_tools(
                messages,
                model,
                policy,
                tools,
                execution_authorization,
                state,
            )

        try:
            async with asyncio.timeout(policy.deadline_seconds):
                final_content = await self._conversation.run_turn(
                    session_id,
                    content,
                    operation,
                )
        except TimeoutError:
            return self._result(
                session_id,
                model,
                policy,
                OrchestrationStatus.TIMEOUT,
                None,
                "orchestration deadline exceeded",
                state,
                started_at,
            )
        except ContextLimitExceededError as error:
            return self._result(
                session_id,
                model,
                policy,
                OrchestrationStatus.CONTEXT_LIMIT,
                None,
                str(error),
                state,
                started_at,
            )
        except InvalidProviderResponseError as error:
            return self._result(
                session_id,
                model,
                policy,
                OrchestrationStatus.INVALID_RESPONSE,
                None,
                str(error),
                state,
                started_at,
            )
        except ProviderUnavailableError as error:
            return self._result(
                session_id,
                model,
                policy,
                OrchestrationStatus.PROVIDER_UNAVAILABLE,
                None,
                str(error),
                state,
                started_at,
            )
        except _TurnStopped as stopped:
            return self._result(
                session_id,
                model,
                policy,
                stopped.status,
                None,
                stopped.failure,
                state,
                started_at,
            )

        return self._result(
            session_id,
            model,
            policy,
            OrchestrationStatus.COMPLETED,
            final_content,
            None,
            state,
            started_at,
        )

    def stream(
        self,
        session_id: UUID,
        content: str,
        *,
        model: str,
        effort: EffortLevel | None = None,
        authorization: ToolAuthorization | None = None,
        selected_tools: Iterable[str] = (),
    ) -> OrchestrationStream:
        """Start real textual streaming while rejecting combined structured tool calling."""

        level = self._default_effort if effort is None else effort
        policy = resolve_effort_policy(level, self._policies)
        active_authorization = authorization or ToolAuthorization()
        tools, _ = self._select_tools(
            selected_tools,
            active_authorization,
            enabled=policy.tools_enabled,
        )

        if not policy.streaming_enabled:
            raise ValueError("streaming is disabled by the selected effort policy")
        if tools:
            raise ValueError("streaming cannot be combined with structured tool calling")

        upstream = self._conversation.stream(
            session_id,
            content,
            model=model,
            thinking=policy.thinking,
            request_validator=self._context.ensure_text_fits,
        )
        return OrchestrationStream(upstream, policy.deadline_seconds)

    async def _generate_text(
        self,
        messages: tuple[Message, ...],
        model: str,
        policy: EffortPolicy,
        state: _MetricsState,
    ) -> str:
        self._context.ensure_text_fits(messages)
        request = InferenceRequest(model, messages, policy.thinking)
        state.inferences_started += 1
        response = await self._provider.generate(request)

        if not isinstance(response, InferenceResponse):
            raise InvalidProviderResponseError("provider returned an invalid response")

        state.inferences_completed += 1
        self._record_provider_metrics(response.metrics, state)
        return response.content

    async def _generate_with_tools(
        self,
        messages: tuple[Message, ...],
        model: str,
        policy: EffortPolicy,
        tools: tuple[ToolDefinition, ...],
        authorization: ToolAuthorization,
        state: _MetricsState,
    ) -> str:
        operational = tuple(
            ToolMessage(ToolMessageRole(message.role.value), message.content)
            for message in messages
        )
        active_user_index = len(operational) - 1
        seen_call_ids: set[str] = set()
        executor = ToolExecutor(self._registry)
        provider = cast(ToolCallingProvider, self._tool_provider)

        while state.inferences_started < policy.max_inferences:
            operational, active_user_index = self._context.fit_tool_messages(
                operational,
                tools,
                active_user_index,
            )
            request = ToolInferenceRequest(model, operational, tools, policy.thinking)
            state.inferences_started += 1
            response = await provider.generate_with_tools(request)

            if not isinstance(response, ToolInferenceResponse):
                raise InvalidProviderResponseError("tool provider returned an invalid response")

            state.inferences_completed += 1
            self._record_provider_metrics(response.metrics, state)
            calls = response.tool_calls
            state.tool_proposals += len(calls)

            duplicate = any(call.call_id in seen_call_ids for call in calls)
            if duplicate:
                raise InvalidProviderResponseError(
                    "tool call identifiers must be unique across one orchestration turn"
                )

            if not calls:
                return response.content
            if state.inferences_started >= policy.max_inferences:
                raise _TurnStopped(
                    OrchestrationStatus.INFERENCE_LIMIT,
                    "the final permitted inference requested additional tools",
                )
            if state.tool_proposals > policy.max_tool_calls:
                raise _TurnStopped(
                    OrchestrationStatus.TOOL_LIMIT,
                    "the proposed tool batch exceeds the remaining tool-call budget",
                )

            seen_call_ids.update(call.call_id for call in calls)
            operational = (*operational, response.as_message())

            for call in calls:
                result = await executor.execute(call, authorization)
                state.tool_results.append(result)
                operational = (*operational, ToolMessage.from_result(result))
                self._record_tool_result(result, state)

        raise _TurnStopped(
            OrchestrationStatus.INFERENCE_LIMIT,
            "the inference limit was reached before a final response",
        )

    def _select_tools(
        self,
        selected_tools: Iterable[str],
        authorization: ToolAuthorization,
        *,
        enabled: bool,
    ) -> tuple[tuple[ToolDefinition, ...], ToolAuthorization]:
        if isinstance(selected_tools, str | bytes) or not isinstance(selected_tools, Iterable):
            raise TypeError("selected_tools must be an iterable of tool names")

        requested = tuple(selected_tools)
        if not all(isinstance(name, str) and name for name in requested):
            raise TypeError("selected tool names must be non-empty strings")
        if len(requested) != len(set(requested)):
            raise ValueError("selected tool names must be unique")
        if not enabled:
            return (), ToolAuthorization()

        requested_names = set(requested)
        definitions = tuple(
            definition
            for definition in self._registry.definitions()
            if definition.name in requested_names and authorization.permits(definition)
        )
        effective_authorization = ToolAuthorization(definition.name for definition in definitions)
        return definitions, effective_authorization

    @staticmethod
    def _detect_tool_provider(provider: LLMProvider) -> ToolCallingProvider | None:
        capability = getattr(provider, "generate_with_tools", None)
        return cast(ToolCallingProvider, provider) if callable(capability) else None

    @staticmethod
    def _validate_policies(
        policies: Mapping[EffortLevel, EffortPolicy],
    ) -> dict[EffortLevel, EffortPolicy]:
        if not isinstance(policies, Mapping):
            raise TypeError("effort_policies must be a mapping")

        validated = dict(policies)
        for level, policy in validated.items():
            if not isinstance(level, EffortLevel) or not isinstance(policy, EffortPolicy):
                raise TypeError("effort policies must map EffortLevel to EffortPolicy")
            if level is not policy.level:
                raise ValueError("effort policy keys must match their policy levels")

        return validated

    @staticmethod
    def _record_provider_metrics(
        metrics: InferenceMetrics | None,
        state: _MetricsState,
    ) -> None:
        if metrics is not None:
            state.inference_metrics.append(metrics)

    @staticmethod
    def _record_tool_result(result: ToolResult, state: _MetricsState) -> None:
        not_invoked = {
            ToolResultStatus.UNKNOWN_TOOL,
            ToolResultStatus.INVALID_ARGUMENTS,
            ToolResultStatus.UNAUTHORIZED,
        }

        if result.status not in not_invoked:
            state.handlers_invoked += 1
        if result.status is ToolResultStatus.SUCCESS:
            state.tools_succeeded += 1
        else:
            state.tools_rejected_or_failed += 1

    @staticmethod
    def _result(
        session_id: UUID,
        model: str,
        policy: EffortPolicy,
        status: OrchestrationStatus,
        content: str | None,
        failure: str | None,
        state: _MetricsState,
        started_at: float,
    ) -> OrchestrationResult:
        metrics = OrchestrationMetrics(
            elapsed_seconds=time.monotonic() - started_at,
            inferences_started=state.inferences_started,
            inferences_completed=state.inferences_completed,
            tool_proposals=state.tool_proposals,
            handlers_invoked=state.handlers_invoked,
            tools_succeeded=state.tools_succeeded,
            tools_rejected_or_failed=state.tools_rejected_or_failed,
            effort=policy.level,
            thinking=policy.thinking,
            inference_metrics=tuple(state.inference_metrics),
        )
        return OrchestrationResult(
            session_id=session_id,
            model=model,
            effort=policy.level,
            status=status,
            content=content,
            tool_results=tuple(state.tool_results),
            metrics=metrics,
            failure=failure,
        )
