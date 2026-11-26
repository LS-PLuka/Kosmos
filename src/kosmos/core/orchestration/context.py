"""Deterministic integrated context budgeting for orchestration requests."""

import json
from dataclasses import dataclass

from kosmos.core.exceptions import ContextLimitExceededError
from kosmos.intelligence.models import Message
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

    def fit_tool_messages(
        self,
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
        active_user_index: int,
    ) -> tuple[tuple[ToolMessage, ...], int]:
        """Drop only the oldest complete confirmed turns until structured context fits."""

        selected = list(messages)
        current_index = active_user_index

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

        return tuple(selected), current_index

    def _tool_payload_fits(
        self,
        messages: tuple[ToolMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> bool:
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

        payload = {
            "messages": message_payloads,
            "tools": [tool.to_provider_schema() for tool in tools],
        }
        return self._serialized_size(payload) <= self._input_limit

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
