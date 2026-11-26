"""Immutable public models for in-memory conversations."""

from dataclasses import dataclass
from uuid import UUID

from kosmos.intelligence.models import Message


@dataclass(frozen=True, slots=True)
class ConversationSession:
    """A read-only snapshot of one managed conversation session."""

    session_id: UUID
    system_instruction: str | None
    messages: tuple[Message, ...]
    is_busy: bool
