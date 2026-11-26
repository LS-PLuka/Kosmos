"""Provider-independent models for text inference."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class MessageRole(str, Enum):
    """Supported roles for the initial text conversation model."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class Message:
    """A validated textual conversation message."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, MessageRole):
            raise TypeError("message role must be a MessageRole")

        _require_non_empty_text(self.content, "message content")


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """An immutable request for complete text generation."""

    model: str
    messages: tuple[Message, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")

        if isinstance(self.messages, str | bytes):
            raise TypeError("messages must be a sequence of Message instances")

        if not isinstance(self.messages, Sequence):
            raise TypeError("messages must be a sequence of Message instances")

        messages = tuple(self.messages)

        if not messages:
            raise ValueError("messages must not be empty")

        if not all(isinstance(message, Message) for message in messages):
            raise TypeError("messages must contain only Message instances")

        object.__setattr__(self, "messages", messages)


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    """A provider-independent complete text inference result."""

    model: str
    content: str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")

        _require_non_empty_text(self.content, "inference response content")


def _require_non_empty_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
