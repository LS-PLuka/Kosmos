"""Deterministic context selection for conversation turns."""

from collections.abc import Sequence
from dataclasses import dataclass

from kosmos.core.config import (
    DEFAULT_CONVERSATION_MAX_CONTEXT_CHARACTERS,
    DEFAULT_CONVERSATION_MAX_HISTORY_TURNS,
)
from kosmos.core.exceptions import ContextLimitExceededError
from kosmos.intelligence.conversation.models import ContextSelection, ContextSelectionMetrics
from kosmos.intelligence.models import Message, MessageRole

DEFAULT_MAX_HISTORY_TURNS = DEFAULT_CONVERSATION_MAX_HISTORY_TURNS
DEFAULT_MAX_CONTEXT_CHARACTERS = DEFAULT_CONVERSATION_MAX_CONTEXT_CHARACTERS


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """Select the newest continuous suffix of complete turns that fits a character budget."""

    max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS
    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS

    def __post_init__(self) -> None:
        if isinstance(self.max_history_turns, bool) or not isinstance(self.max_history_turns, int):
            raise TypeError("max_history_turns must be an integer")

        if self.max_history_turns < 0:
            raise ValueError("max_history_turns must not be negative")

        if isinstance(self.max_context_characters, bool) or not isinstance(
            self.max_context_characters, int
        ):
            raise TypeError("max_context_characters must be an integer")

        if self.max_context_characters <= 0:
            raise ValueError("max_context_characters must be greater than zero")

    def select(
        self,
        *,
        system_instruction: str | None,
        history: Sequence[Message],
        current_message: Message,
    ) -> tuple[Message, ...]:
        """Build context without modifying the complete confirmed history."""

        return self.select_with_metrics(
            system_instruction=system_instruction,
            history=history,
            current_message=current_message,
        ).messages

    def select_with_metrics(
        self,
        *,
        system_instruction: str | None,
        history: Sequence[Message],
        current_message: Message,
    ) -> ContextSelection:
        """Build context and report content-only selection measurements."""

        system_message = self._create_system_message(system_instruction)
        self._validate_current_message(current_message)
        turns = self._validate_history(history)

        required_messages = tuple(
            message for message in (system_message, current_message) if message is not None
        )
        required_characters = sum(len(message.content) for message in required_messages)

        if required_characters > self.max_context_characters:
            raise ContextLimitExceededError(
                "system instruction and current message exceed the context character limit"
            )

        selected_reversed: list[tuple[Message, Message]] = []
        used_characters = required_characters

        eligible_turns = turns[-self.max_history_turns :] if self.max_history_turns else ()

        for turn in reversed(eligible_turns):
            turn_characters = len(turn[0].content) + len(turn[1].content)

            if used_characters + turn_characters > self.max_context_characters:
                break

            selected_reversed.append(turn)
            used_characters += turn_characters

        selected_messages = tuple(
            message for turn in reversed(selected_reversed) for message in turn
        )

        messages = (
            (*selected_messages, current_message)
            if system_message is None
            else (system_message, *selected_messages, current_message)
        )
        total_turns = len(turns)
        eligible_count = len(eligible_turns)
        selected_count = len(selected_reversed)
        omitted_by_turn_limit = total_turns - eligible_count
        omitted_by_character_limit = eligible_count - selected_count
        metrics = ContextSelectionMetrics(
            total_confirmed_turns=total_turns,
            eligible_history_turns=eligible_count,
            selected_history_turns=selected_count,
            omitted_history_turns=total_turns - selected_count,
            omitted_by_turn_limit=omitted_by_turn_limit,
            omitted_by_character_limit=omitted_by_character_limit,
            character_budget=self.max_context_characters,
            selected_message_characters=used_characters,
            context_limit_reached=omitted_by_character_limit > 0,
        )
        return ContextSelection(messages, metrics)

    @staticmethod
    def _create_system_message(system_instruction: str | None) -> Message | None:
        if system_instruction is None:
            return None

        return Message(MessageRole.SYSTEM, system_instruction)

    @staticmethod
    def _validate_current_message(message: Message) -> None:
        if not isinstance(message, Message):
            raise TypeError("current_message must be a Message")

        if message.role is not MessageRole.USER:
            raise ValueError("current_message must have the USER role")

    @staticmethod
    def _validate_history(history: Sequence[Message]) -> tuple[tuple[Message, Message], ...]:
        if isinstance(history, str | bytes) or not isinstance(history, Sequence):
            raise TypeError("history must be a sequence of Message instances")

        messages = tuple(history)

        if not all(isinstance(message, Message) for message in messages):
            raise TypeError("history must contain only Message instances")

        if len(messages) % 2:
            raise ValueError("history must contain complete USER and ASSISTANT turns")

        turns: list[tuple[Message, Message]] = []

        for index in range(0, len(messages), 2):
            user_message = messages[index]
            assistant_message = messages[index + 1]

            if (
                user_message.role is not MessageRole.USER
                or assistant_message.role is not MessageRole.ASSISTANT
            ):
                raise ValueError("history must contain ordered USER and ASSISTANT turns")

            turns.append((user_message, assistant_message))

        return tuple(turns)
