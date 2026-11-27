"""Immutable public models for in-memory conversations."""

from dataclasses import dataclass
from uuid import UUID

from kosmos.intelligence.models import Message


@dataclass(frozen=True, slots=True)
class ContextSelectionMetrics:
    """Content-only measurements from one deterministic history selection."""

    total_confirmed_turns: int
    eligible_history_turns: int
    selected_history_turns: int
    omitted_history_turns: int
    omitted_by_turn_limit: int
    omitted_by_character_limit: int
    character_budget: int
    selected_message_characters: int
    context_limit_reached: bool


@dataclass(frozen=True, slots=True)
class ContextSelection:
    """Selected inference messages and their privacy-safe measurements."""

    messages: tuple[Message, ...]
    metrics: ContextSelectionMetrics


@dataclass(frozen=True, slots=True)
class ConversationSession:
    """A read-only snapshot of one managed conversation session."""

    session_id: UUID
    system_instruction: str | None
    messages: tuple[Message, ...]
    is_busy: bool
