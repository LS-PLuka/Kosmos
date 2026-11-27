"""Official behavioral identity of Kosmos."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssistantIdentity:
    """Immutable product identity used by conversational personality instructions."""

    name: str
    slogan: str
    purpose: str


KOSMOS_IDENTITY = AssistantIdentity(
    name="Kosmos",
    slogan="The intelligence orbiting your world.",
    purpose="a personal AI assistant for activities, decisions, and projects",
)
