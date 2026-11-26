"""Parsing for trusted local commands that never reach the language model."""

from dataclasses import dataclass
from enum import Enum

from kosmos.core.orchestration import EffortLevel


class CommandName(str, Enum):
    """Supported local command names."""

    HELP = "help"
    STATUS = "status"
    EFFORT = "effort"
    METRICS = "metrics"
    TOOLS = "tools"
    CLEAR = "clear"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class LocalCommand:
    """One validated local command and its optional value."""

    name: CommandName
    value: str | None = None


class CommandError(ValueError):
    """Raised when a local command cannot be parsed safely."""


def parse_local_command(content: str) -> LocalCommand | None:
    """Parse slash-prefixed input without aliases or shell interpretation."""

    if not content.startswith("/"):
        return None

    parts = content.split()
    command_text = parts[0][1:].lower()

    try:
        name = CommandName(command_text)
    except ValueError:
        raise CommandError(f"unknown command: /{command_text}") from None

    arguments = parts[1:]
    if name in {
        CommandName.HELP,
        CommandName.STATUS,
        CommandName.TOOLS,
        CommandName.CLEAR,
        CommandName.EXIT,
    }:
        if arguments:
            raise CommandError(f"/{name.value} does not accept arguments")
        return LocalCommand(name)

    if len(arguments) > 1:
        raise CommandError(f"/{name.value} accepts at most one argument")

    value = arguments[0].lower() if arguments else None
    if name is CommandName.EFFORT and value is not None:
        supported = {level.value for level in supported_effort_levels()}
        if value not in supported:
            raise CommandError(
                f"unsupported effort level: {value}; choose instant, low, medium, or high"
            )

    if name is CommandName.METRICS and value not in {None, "on", "off"}:
        raise CommandError("/metrics accepts only 'on' or 'off'")

    return LocalCommand(name, value)


def supported_effort_levels() -> tuple[EffortLevel, ...]:
    """Return only the effort levels available to the development CLI."""

    return (
        EffortLevel.INSTANT,
        EffortLevel.LOW,
        EffortLevel.MEDIUM,
        EffortLevel.HIGH,
    )
