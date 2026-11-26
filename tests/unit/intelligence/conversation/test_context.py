"""Tests for deterministic conversation context selection."""

import pytest

from kosmos.core.exceptions import ContextLimitExceededError
from kosmos.intelligence.conversation import ContextPolicy
from kosmos.intelligence.models import Message, MessageRole


def _message(role: MessageRole, content: str) -> Message:
    return Message(role, content)


def _history(*contents: str) -> tuple[Message, ...]:
    messages: list[Message] = []

    for index, content in enumerate(contents):
        role = MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT
        messages.append(_message(role, content))

    return tuple(messages)


def test_context_contains_system_history_and_current_message_in_order() -> None:
    policy = ContextPolicy()
    history = _history("first question", "first answer")
    current = _message(MessageRole.USER, "second question")

    context = policy.select(
        system_instruction="Follow the explicit instructions.",
        history=history,
        current_message=current,
    )

    assert [message.role for message in context] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.USER,
    ]
    assert [message.content for message in context] == [
        "Follow the explicit instructions.",
        "first question",
        "first answer",
        "second question",
    ]


def test_context_omits_system_message_when_instruction_is_absent() -> None:
    current = _message(MessageRole.USER, "question")

    context = ContextPolicy().select(
        system_instruction=None,
        history=(),
        current_message=current,
    )

    assert context == (current,)


def test_turn_limit_selects_most_recent_complete_turns() -> None:
    history = _history("u1", "a1", "u2", "a2", "u3", "a3")
    current = _message(MessageRole.USER, "u4")

    context = ContextPolicy(max_history_turns=2).select(
        system_instruction=None,
        history=history,
        current_message=current,
    )

    assert [message.content for message in context] == ["u2", "a2", "u3", "a3", "u4"]


def test_zero_turn_limit_sends_only_required_messages() -> None:
    current = _message(MessageRole.USER, "current")

    context = ContextPolicy(max_history_turns=0).select(
        system_instruction="system",
        history=_history("old user", "old assistant"),
        current_message=current,
    )

    assert [message.content for message in context] == ["system", "current"]


def test_character_limit_selects_a_continuous_recent_suffix() -> None:
    history = _history("11", "22", "333", "444", "5", "6")
    current = _message(MessageRole.USER, "now")

    context = ContextPolicy(max_context_characters=12).select(
        system_instruction=None,
        history=history,
        current_message=current,
    )

    assert [message.content for message in context] == ["333", "444", "5", "6", "now"]


def test_oversized_recent_turn_prevents_selecting_older_turns() -> None:
    history = _history("a", "b", "recent user", "recent assistant")
    current = _message(MessageRole.USER, "now")

    context = ContextPolicy(max_context_characters=8).select(
        system_instruction=None,
        history=history,
        current_message=current,
    )

    assert context == (current,)


def test_selection_does_not_modify_history() -> None:
    history = _history("first", "answer", "second", "answer")
    original = tuple(history)

    ContextPolicy(max_history_turns=1).select(
        system_instruction=None,
        history=history,
        current_message=_message(MessageRole.USER, "current"),
    )

    assert history == original


def test_required_messages_over_budget_raise_explicit_error() -> None:
    with pytest.raises(ContextLimitExceededError, match="context character limit"):
        ContextPolicy(max_context_characters=5).select(
            system_instruction="abc",
            history=(),
            current_message=_message(MessageRole.USER, "def"),
        )


@pytest.mark.parametrize("value", [True, 1.5, "10"])
def test_turn_limit_rejects_incorrect_types(value: object) -> None:
    with pytest.raises(TypeError, match="max_history_turns"):
        ContextPolicy(max_history_turns=value)  # type: ignore[arg-type]


def test_turn_limit_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="max_history_turns"):
        ContextPolicy(max_history_turns=-1)


@pytest.mark.parametrize("value", [True, 1.5, "6000"])
def test_character_limit_rejects_incorrect_types(value: object) -> None:
    with pytest.raises(TypeError, match="max_context_characters"):
        ContextPolicy(max_context_characters=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1])
def test_character_limit_rejects_non_positive_values(value: int) -> None:
    with pytest.raises(ValueError, match="max_context_characters"):
        ContextPolicy(max_context_characters=value)


def test_context_rejects_incomplete_or_misordered_history() -> None:
    policy = ContextPolicy()
    current = _message(MessageRole.USER, "current")

    with pytest.raises(ValueError, match="complete"):
        policy.select(
            system_instruction=None,
            history=(_message(MessageRole.USER, "unanswered"),),
            current_message=current,
        )

    with pytest.raises(ValueError, match="ordered"):
        policy.select(
            system_instruction=None,
            history=(
                _message(MessageRole.ASSISTANT, "wrong"),
                _message(MessageRole.USER, "order"),
            ),
            current_message=current,
        )


def test_context_rejects_non_user_current_message() -> None:
    with pytest.raises(ValueError, match="USER"):
        ContextPolicy().select(
            system_instruction=None,
            history=(),
            current_message=_message(MessageRole.SYSTEM, "not user input"),
        )
