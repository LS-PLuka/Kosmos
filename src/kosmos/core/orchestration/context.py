"""Deterministic integrated context budgeting for orchestration requests."""

import json
from dataclasses import dataclass

from kosmos.core.exceptions import ContextLimitExceededError
from kosmos.core.orchestration.models import ContextRequestMetrics
from kosmos.intelligence.models import Message, MessageRole
from kosmos.intelligence.tools.models import (
    ToolDefinition,
    ToolMessage,
    ToolMessageRole,
    thaw_json,
)

DEFAULT_MAX_CONTEXT_CHARACTERS = 12_000
DEFAULT_RESPONSE_RESERVE_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class OrchestrationContextPolicy:
    """Fit complete confirmed turns while preserving active-turn structured data."""

    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS
    response_reserve_characters: int = DEFAULT_RESPONSE_RESERVE_CHARACTERS

    def __post_init__(self) -> None:
        for field_name in ("max_context_characters", "response_reserve_characters"):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")

        if self.max_context_characters <= 0:
            raise ValueError("max_context_characters must be greater than zero")
        if self.response_reserve_characters >= self.max_context_characters:
            raise ValueError("response reserve must be smaller than the context limit")

    def ensure_text_fits(self, messages: tuple[Message, ...]) -> None:
        """Reject a textual request whose complete selected context exceeds the budget."""

        payload = [{"role": message.role.value, "content": message.content} for message in messages]
        self._ensure_size(payload)

    def fit_text_messages(
        self,
        messages: tuple[Message, ...],
    ) -> tuple[tuple[Message, ...], ContextRequestMetrics]:
        """Fit serialized text context by removing only oldest complete history turns."""

        selected = list(messages)
        omitted_turns = 0

        while not self._text_payload_fits(tuple(selected)):
            history_start = int(bool(selected) and selected[0].role is MessageRole.SYSTEM)

            if history_start + 1 >= len(selected) - 1:
                raise ContextLimitExceededError(
                    "required messages exceed the orchestration context limit"
                )

            first = selected[history_start]
            second = selected[history_start + 1]
            if first.role is not MessageRole.USER or second.role is not MessageRole.ASSISTANT:
                raise ValueError("confirmed history must contain complete ordered turns")

            del selected[history_start : history_start + 2]
            omitted_turns += 1

        fitted = tuple(selected)
        payload = self._text_payload(fitted)
        metrics = self._metrics("text", fitted, payload, omitted_turns)
        return fitted, metrics

    def fit_tool_messages(
        self,
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
        active_user_index: int,
    ) -> tuple[tuple[ToolMessage, ...], int]:
        """Fit structured context while preserving the original public return contract."""

        fitted, current_index, _ = self.fit_tool_messages_with_metrics(
            messages,
            tools,
            active_user_index,
        )
        return fitted, current_index

    def fit_tool_messages_with_metrics(
        self,
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
        active_user_index: int,
    ) -> tuple[tuple[ToolMessage, ...], int, ContextRequestMetrics]:
        """Drop only the oldest complete confirmed turns until structured context fits."""

        selected = list(messages)
        current_index = active_user_index
        omitted_turns = 0

        while not self._tool_payload_fits(tuple(selected), tools):
            history_start = int(bool(selected) and selected[0].role is ToolMessageRole.SYSTEM)

            if history_start + 1 >= current_index:
                raise ContextLimitExceededError(
                    "required active-turn data exceeds the orchestration context limit"
                )

            first = selected[history_start]
            second = selected[history_start + 1]

            invalid_turn = (
                first.role is not ToolMessageRole.USER
                or second.role is not ToolMessageRole.ASSISTANT
            )
            if invalid_turn:
                raise ValueError("confirmed history must contain complete ordered turns")

            del selected[history_start : history_start + 2]
            current_index -= 2
            omitted_turns += 1

        fitted = tuple(selected)
        payload = self._tool_payload(fitted, tools)
        metrics = self._metrics("tools", fitted, payload, omitted_turns)
        return fitted, current_index, metrics

    def _text_payload_fits(self, messages: tuple[Message, ...]) -> bool:
        return self._serialized_size(self._text_payload(messages)) <= self._input_limit

    @staticmethod
    def _text_payload(messages: tuple[Message, ...]) -> list[dict[str, str]]:
        return [{"role": message.role.value, "content": message.content} for message in messages]

    def _tool_payload_fits(
        self,
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> bool:
        return self._serialized_size(self._tool_payload(messages, tools)) <= self._input_limit

    @staticmethod
    def _tool_payload(
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> dict[str, object]:
        message_payloads = []

        for message in messages:
            payload: dict[str, object] = {
                "role": message.role.value,
                "content": message.content,
            }
            if message.tool_calls:
                payload["tool_calls"] = [
                    {
                        "id": call.call_id,
                        "name": call.name,
                        "arguments": thaw_json(call.arguments),
                    }
                    for call in message.tool_calls
                ]
            if message.tool_name is not None:
                payload["tool_name"] = message.tool_name

            message_payloads.append(payload)

        return {
            "messages": message_payloads,
            "tools": [tool.to_provider_schema() for tool in tools],
        }

    def _metrics(
        self,
        request_kind: str,
        messages: tuple[Message, ...] | tuple[ToolMessage, ...],
        payload: object,
        omitted_turns: int,
    ) -> ContextRequestMetrics:
        return ContextRequestMetrics(
            request_kind=request_kind,
            character_budget=self._input_limit,
            serialized_request_characters=self._serialized_size(payload),
            selected_message_characters=sum(len(message.content) for message in messages),
            response_reserve_characters=self.response_reserve_characters,
            omitted_history_turns=omitted_turns,
            context_limit_reached=omitted_turns > 0,
        )

    def _ensure_size(self, payload: object) -> None:
        if self._serialized_size(payload) > self._input_limit:
            raise ContextLimitExceededError(
                "required messages exceed the orchestration context limit"
            )

    @property
    def _input_limit(self) -> int:
        return self.max_context_characters - self.response_reserve_characters

    @staticmethod
    def _serialized_size(payload: object) -> int:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return len(serialized)
