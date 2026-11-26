"""Provider-independent behavioral identity and system instructions."""

from kosmos.intelligence.personality.engine import PersonalityEngine
from kosmos.intelligence.personality.identity import KOSMOS_IDENTITY, AssistantIdentity
from kosmos.intelligence.personality.models import PersonalityProfile
from kosmos.intelligence.personality.principles import PERMANENT_PRINCIPLES

__all__ = [
    "KOSMOS_IDENTITY",
    "PERMANENT_PRINCIPLES",
    "AssistantIdentity",
    "PersonalityEngine",
    "PersonalityProfile",
]
