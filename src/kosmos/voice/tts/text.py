"""Conservative deterministic preparation of display text for speech."""

import re
import unicodedata

from kosmos.voice.exceptions import InvalidSynthesisRequestError
from kosmos.voice.tts.models import MAX_SEGMENT_CHARACTERS, MAX_TEXT_CHARACTERS

_FENCE = re.compile(r"```(?:[^\n`]*)\n?(.*?)```", re.DOTALL)
_LINK = re.compile(r"!?\[([^\]]+)\]\([^\s)]+(?:\s+[^)]*)?\)")
_HEADING_OR_LIST = re.compile(r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
_EMPHASIS = re.compile(r"(?<!\\)(?:\*\*|__|~~|(?<!\*)\*(?!\*)|(?<!_)_(?!_))")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_WHITESPACE = re.compile(r"[^\S\n]+")
_MANY_NEWLINES = re.compile(r"\n{2,}")


def prepare_text(text: str) -> str:
    """Remove visual markup while retaining code content and semantic values."""

    if not isinstance(text, str) or not text.strip():
        raise InvalidSynthesisRequestError("Synthesis text must not be empty")
    if len(text) > MAX_TEXT_CHARACTERS:
        raise InvalidSynthesisRequestError(
            f"Synthesis text exceeds the {MAX_TEXT_CHARACTERS}-character request limit"
        )

    prepared = _FENCE.sub(lambda match: f"Code block. {match.group(1).strip()}", text)
    prepared = _LINK.sub(r"\1", prepared)
    prepared = _HEADING_OR_LIST.sub("", prepared)
    prepared = _INLINE_CODE.sub(r"\1", prepared)
    prepared = _EMPHASIS.sub("", prepared)
    prepared = prepared.replace("[[", "[ [").replace("]]", "] ]")
    prepared = "".join(
        character
        for character in prepared
        if character in "\n\t" or not unicodedata.category(character).startswith("C")
    )
    prepared = _WHITESPACE.sub(" ", prepared)
    prepared = _MANY_NEWLINES.sub("\n", prepared).strip()
    if not prepared:
        raise InvalidSynthesisRequestError("Synthesis text is empty after safe preparation")

    return prepared


def segment_text(text: str, *, max_characters: int = MAX_SEGMENT_CHARACTERS) -> tuple[str, ...]:
    """Split prepared text on natural boundaries without loss or duplication."""

    if (
        isinstance(max_characters, bool)
        or not isinstance(max_characters, int)
        or max_characters < 32
    ):
        raise InvalidSynthesisRequestError("Segment limit must be an integer of at least 32")
    prepared = prepare_text(text)
    if len(prepared) <= max_characters:
        return (prepared,)

    segments: list[str] = []
    remainder = prepared
    while remainder:
        if len(remainder) <= max_characters:
            segments.append(remainder)
            break

        window = remainder[: max_characters + 1]
        split_at = max(window.rfind(mark) + 1 for mark in (". ", "! ", "? ", "; ", ": ", "\n"))
        if split_at <= 0:
            split_at = window.rfind(" ")
        if split_at <= 0:
            raise InvalidSynthesisRequestError(
                "A word exceeds the configured synthesis segment limit"
            )

        segment = remainder[:split_at].strip()
        if segment:
            segments.append(segment)
        remainder = remainder[split_at:].strip()

    return tuple(segments)
