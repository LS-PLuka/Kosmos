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


def test_default_context_budget_is_eight_thousand_characters() -> None:
    policy = ContextPolicy()

    assert policy.max_history_turns == 10
    assert policy.max_context_characters == 8_000


def test_proposed_budget_retains_more_complete_turns_than_previous_budget() -> None:
    history = tuple(
        message
        for turn in range(8)
        for message in (
            Message(MessageRole.USER, f"fact-{turn}:" + "u" * 293),
            Message(MessageRole.ASSISTANT, "a" * 300),
        )
    )
    current = Message(MessageRole.USER, "q" * 100)

    previous = ContextPolicy(max_context_characters=6_000).select_with_metrics(
        system_instruction="s" * 2_500,
        history=history,
        current_message=current,
    )
    proposed = ContextPolicy(max_context_characters=8_000).select_with_metrics(
        system_instruction="s" * 2_500,
        history=history,
        current_message=current,
    )

    assert previous.metrics.total_confirmed_turns == 8
    assert previous.metrics.selected_history_turns == 5
    assert previous.metrics.omitted_by_character_limit == 3
    assert previous.metrics.selected_message_characters == 5_600
    assert all("fact-0:" not in message.content for message in previous.messages)
    assert proposed.metrics.selected_history_turns == 8
    assert proposed.metrics.omitted_history_turns == 0
    assert proposed.metrics.selected_message_characters == 7_400
    assert any("fact-0:" in message.content for message in proposed.messages)


def test_selection_metrics_separate_turn_and_character_omissions_without_content() -> None:
    history = tuple(
        message
        for turn in range(4)
        for message in (
            Message(MessageRole.USER, f"private-{turn}"),
            Message(MessageRole.ASSISTANT, "response"),
        )
    )

    selection = ContextPolicy(max_history_turns=3, max_context_characters=35).select_with_metrics(
        system_instruction=None,
        history=history,
        current_message=Message(MessageRole.USER, "current"),
    )
    metrics = selection.metrics

    assert metrics.total_confirmed_turns == 4
    assert metrics.eligible_history_turns == 3
    assert metrics.selected_history_turns == 1
    assert metrics.omitted_history_turns == 3
    assert metrics.omitted_by_turn_limit == 1
    assert metrics.omitted_by_character_limit == 2
    assert metrics.context_limit_reached is True
    assert "private" not in repr(metrics)


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
