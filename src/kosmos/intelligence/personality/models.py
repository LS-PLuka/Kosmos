"""Validated personality configuration independent of language model providers."""

import re
from dataclasses import dataclass

DEFAULT_LANGUAGE = "pt-BR"
DEFAULT_HONORIFIC = "senhor"

_LANGUAGE_PATTERN = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")
_MAX_LANGUAGE_LENGTH = 35
_MAX_HONORIFIC_LENGTH = 24


@dataclass(frozen=True, slots=True)
class PersonalityProfile:
    """Immutable communication preferences for one conversational session."""

    formality: int = 45
    directness: int = 90
    humor: int = 45
    sarcasm: int = 25
    proactivity: int = 85
    assertiveness: int = 80
    emotional_expressiveness: int = 45
    detail_level: int = 40
    preferred_language: str = DEFAULT_LANGUAGE
    honorific: str | None = DEFAULT_HONORIFIC

    def __post_init__(self) -> None:
        for field_name in (
            "formality",
            "directness",
            "humor",
            "sarcasm",
            "proactivity",
            "assertiveness",
            "emotional_expressiveness",
            "detail_level",
        ):
            _validate_trait(getattr(self, field_name), field_name)

        _validate_language(self.preferred_language)
        _validate_honorific(self.honorific)


def _validate_trait(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")

    if not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100")


def _validate_language(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("preferred_language must be a string")

    if len(value) > _MAX_LANGUAGE_LENGTH or _LANGUAGE_PATTERN.fullmatch(value) is None:
        raise ValueError("preferred_language must be a valid language tag")


def _validate_honorific(value: object) -> None:
    if value is None:
        return

    if not isinstance(value, str):
        raise TypeError("honorific must be a string or None")

    if not value or value != value.strip() or len(value) > _MAX_HONORIFIC_LENGTH:
        raise ValueError("honorific must be non-empty, trimmed, and at most 24 characters")

    if not all(character.isalpha() or character in ".-'" for character in value):
        raise ValueError("honorific contains unsupported characters")
