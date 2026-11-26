"""Behavioral tests for provider-independent inference models."""

from dataclasses import FrozenInstanceError

import pytest

from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
    Message,
    MessageRole,
)


def test_creates_valid_text_messages_with_lowercase_wire_values() -> None:
    message = Message(MessageRole.USER, "Hello")

    assert message.role.value == "user"
    assert message.content == "Hello"


def test_rejects_invalid_message_roles_at_runtime() -> None:
    with pytest.raises(TypeError, match="MessageRole"):
        Message("user", "Hello")  # type: ignore[arg-type]


@pytest.mark.parametrize("model", ["", "   "])
def test_rejects_requests_without_a_model(model: str) -> None:
    with pytest.raises(ValueError, match="model"):
        InferenceRequest(model, (Message(MessageRole.USER, "Hello"),))


def test_rejects_empty_or_invalid_message_collections() -> None:
    with pytest.raises(ValueError, match="messages"):
        InferenceRequest("test-model", ())

    with pytest.raises(TypeError, match="Message"):
        InferenceRequest("test-model", ("not-a-message",))  # type: ignore[arg-type]


def test_preserves_message_order_and_copies_mutable_input() -> None:
    first = Message(MessageRole.SYSTEM, "Be concise")
    second = Message(MessageRole.USER, "Hello")
    source = [first, second]

    request = InferenceRequest("test-model", source)  # type: ignore[arg-type]
    source.reverse()

    assert request.messages == (first, second)


def test_models_are_immutable() -> None:
    message = Message(MessageRole.ASSISTANT, "Hello")
    request = InferenceRequest("test-model", (message,))
    response = InferenceResponse("test-model", "Hello")

    with pytest.raises(FrozenInstanceError):
        message.content = "Changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        request.model = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        response.content = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize("content", ["", "   "])
def test_rejects_empty_text_content(content: str) -> None:
    with pytest.raises(ValueError, match="content"):
        Message(MessageRole.USER, content)

    with pytest.raises(ValueError, match="content"):
        InferenceResponse("test-model", content)


def test_request_thinking_is_optional_and_strictly_boolean() -> None:
    message = Message(MessageRole.USER, "Hello")

    assert InferenceRequest("test-model", (message,)).thinking is None
    assert InferenceRequest("test-model", (message,), thinking=False).thinking is False

    with pytest.raises(TypeError, match="thinking"):
        InferenceRequest("test-model", (message,), thinking=1)  # type: ignore[arg-type]


def test_chunk_allows_empty_and_whitespace_content() -> None:
    assert InferenceChunk("test-model", "").content == ""
    assert InferenceChunk("test-model", " ").content == " "


def test_metrics_validate_non_negative_integer_values() -> None:
    metrics = InferenceMetrics(total_duration_ns=10, eval_count=2)

    assert metrics.total_duration_ns == 10
    assert metrics.eval_count == 2

    with pytest.raises(ValueError, match="negative"):
        InferenceMetrics(eval_count=-1)

    with pytest.raises(TypeError, match="integer"):
        InferenceMetrics(eval_count=True)  # type: ignore[arg-type]
