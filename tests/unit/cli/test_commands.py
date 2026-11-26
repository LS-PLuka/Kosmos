"""Tests for trusted local command parsing."""

import pytest

from kosmos.cli.commands import CommandError, CommandName, parse_local_command


@pytest.mark.parametrize(
    ("content", "name"),
    [
        ("/help", CommandName.HELP),
        ("/status", CommandName.STATUS),
        ("/tools", CommandName.TOOLS),
        ("/clear", CommandName.CLEAR),
        ("/exit", CommandName.EXIT),
    ],
)
def test_parses_argument_free_commands(content: str, name: CommandName) -> None:
    command = parse_local_command(content)

    assert command is not None
    assert command.name is name
    assert command.value is None


@pytest.mark.parametrize("level", ["instant", "low", "medium", "high"])
def test_parses_supported_effort_levels(level: str) -> None:
    command = parse_local_command(f"/effort {level}")

    assert command is not None
    assert command.name is CommandName.EFFORT
    assert command.value == level


@pytest.mark.parametrize("value", ["on", "off"])
def test_parses_explicit_metrics_state(value: str) -> None:
    command = parse_local_command(f"/metrics {value}")

    assert command is not None
    assert command.value == value


def test_non_command_is_not_consumed() -> None:
    assert parse_local_command("Explain /help") is None


@pytest.mark.parametrize(
    "content",
    [
        "/unknown",
        "/help unexpected",
        "/exit now",
        "/effort expert",
        "/effort auto",
        "/metrics maybe",
        "/metrics on now",
    ],
)
def test_rejects_unknown_or_invalid_commands(content: str) -> None:
    with pytest.raises(CommandError):
        parse_local_command(content)
