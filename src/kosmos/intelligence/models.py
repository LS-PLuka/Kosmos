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
    """An immutable request for text generation."""

    model: str
    messages: tuple[Message, ...]
    thinking: bool | None = None

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

        if self.thinking is not None and not isinstance(self.thinking, bool):
            raise TypeError("thinking must be a boolean or None")

        object.__setattr__(self, "messages", messages)


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    """A provider-independent complete text inference result."""

    model: str
    content: str
    metrics: "InferenceMetrics | None" = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")

        _require_non_empty_text(self.content, "inference response content")

        if self.metrics is not None and not isinstance(self.metrics, InferenceMetrics):
            raise TypeError("metrics must be InferenceMetrics or None")


@dataclass(frozen=True, slots=True)
class InferenceMetrics:
    """Optional Ollama-neutral counts and durations, with durations in nanoseconds."""

    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_count: int | None = None
    eval_duration_ns: int | None = None

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)

            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise TypeError(f"{field_name} must be an integer or None")

            if value is not None and value < 0:
                raise ValueError(f"{field_name} must not be negative")


@dataclass(frozen=True, slots=True)
class InferenceChunk:
    """One ordered text fragment or completion event from streaming inference."""

    model: str
    content: str
    done: bool = False
    metrics: InferenceMetrics | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.model, "model")

        if not isinstance(self.content, str):
            raise TypeError("inference chunk content must be a string")

        if not isinstance(self.done, bool):
            raise TypeError("inference chunk done must be a boolean")

        if self.metrics is not None and not isinstance(self.metrics, InferenceMetrics):
            raise TypeError("metrics must be InferenceMetrics or None")


def _require_non_empty_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
