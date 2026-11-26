"""Explicit, side-effect-free application configuration."""

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

from kosmos.core.exceptions import ConfigurationError

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120.0
DEFAULT_OLLAMA_CONTEXT_LENGTH = 4096
DEFAULT_OLLAMA_THINKING = False
DEFAULT_OLLAMA_KEEP_ALIVE = "5m"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b-q4_K_M"
DEFAULT_CONVERSATION_MAX_HISTORY_TURNS = 10
DEFAULT_CONVERSATION_MAX_CONTEXT_CHARACTERS = 8_000
_KEEP_ALIVE_PATTERN = re.compile(r"(?:0|(?:\d+(?:\.\d+)?)(?:ms|s|m|h))\Z")


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """Validated settings used by the current application foundations."""

    log_level: str = "INFO"
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    ollama_model: str | None = None
    ollama_context_length: int = DEFAULT_OLLAMA_CONTEXT_LENGTH
    ollama_thinking: bool = DEFAULT_OLLAMA_THINKING
    ollama_keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    conversation_max_history_turns: int = DEFAULT_CONVERSATION_MAX_HISTORY_TURNS
    conversation_max_context_characters: int = DEFAULT_CONVERSATION_MAX_CONTEXT_CHARACTERS

    def __post_init__(self) -> None:
        log_level = _validate_log_level(self.log_level)
        base_url = _validate_loopback_url(self.ollama_base_url)
        timeout = _validate_timeout(self.ollama_timeout_seconds)
        model = _validate_optional_model(self.ollama_model)
        context_length = _validate_context_length(self.ollama_context_length)
        thinking = _validate_thinking(self.ollama_thinking)
        keep_alive = _validate_keep_alive(self.ollama_keep_alive)
        history_turns = _validate_non_negative_integer(
            self.conversation_max_history_turns,
            "conversation history turns",
        )
        context_characters = _validate_positive_integer(
            self.conversation_max_context_characters,
            "conversation context characters",
        )

        object.__setattr__(self, "log_level", log_level)
        object.__setattr__(self, "ollama_base_url", base_url)
        object.__setattr__(self, "ollama_timeout_seconds", timeout)
        object.__setattr__(self, "ollama_model", model)
        object.__setattr__(self, "ollama_context_length", context_length)
        object.__setattr__(self, "ollama_thinking", thinking)
        object.__setattr__(self, "ollama_keep_alive", keep_alive)
        object.__setattr__(self, "conversation_max_history_turns", history_turns)
        object.__setattr__(self, "conversation_max_context_characters", context_characters)


def load_settings(environment: Mapping[str, str] | None = None) -> ApplicationSettings:
    """Load settings from an explicit mapping or a snapshot of the process environment."""

    values = dict(os.environ if environment is None else environment)

    timeout = _parse_timeout(
        values.get("KOSMOS_OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_OLLAMA_TIMEOUT_SECONDS))
    )
    context_length = _parse_context_length(
        values.get("KOSMOS_OLLAMA_CONTEXT_LENGTH", str(DEFAULT_OLLAMA_CONTEXT_LENGTH))
    )
    thinking = _parse_thinking(
        values.get("KOSMOS_OLLAMA_THINKING", str(DEFAULT_OLLAMA_THINKING).lower())
    )
    history_turns = _parse_non_negative_integer(
        values.get(
            "KOSMOS_CONVERSATION_MAX_HISTORY_TURNS",
            str(DEFAULT_CONVERSATION_MAX_HISTORY_TURNS),
        ),
        "KOSMOS_CONVERSATION_MAX_HISTORY_TURNS",
    )
    context_characters = _parse_positive_integer(
        values.get(
            "KOSMOS_CONVERSATION_MAX_CONTEXT_CHARACTERS",
            str(DEFAULT_CONVERSATION_MAX_CONTEXT_CHARACTERS),
        ),
        "KOSMOS_CONVERSATION_MAX_CONTEXT_CHARACTERS",
    )

    return ApplicationSettings(
        log_level=values.get("KOSMOS_LOG_LEVEL", "INFO"),
        ollama_base_url=values.get("KOSMOS_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        ollama_timeout_seconds=timeout,
        ollama_model=values.get("KOSMOS_OLLAMA_MODEL"),
        ollama_context_length=context_length,
        ollama_thinking=thinking,
        ollama_keep_alive=values.get("KOSMOS_OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE),
        conversation_max_history_turns=history_turns,
        conversation_max_context_characters=context_characters,
    )


def _parse_timeout(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ConfigurationError("KOSMOS_OLLAMA_TIMEOUT_SECONDS must be a number") from None


def _parse_context_length(value: object) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise ConfigurationError("KOSMOS_OLLAMA_CONTEXT_LENGTH must be a positive integer")

    return int(value)


def _parse_non_negative_integer(value: object, setting_name: str) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise ConfigurationError(f"{setting_name} must be a non-negative integer")

    return int(value)


def _parse_positive_integer(value: object, setting_name: str) -> int:
    parsed = _parse_non_negative_integer(value, setting_name)

    if parsed == 0:
        raise ConfigurationError(f"{setting_name} must be a positive integer")

    return parsed


def _parse_thinking(value: object) -> bool:
    if not isinstance(value, str):
        raise ConfigurationError("KOSMOS_OLLAMA_THINKING must be true or false")

    normalized = value.strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    raise ConfigurationError("KOSMOS_OLLAMA_THINKING must be true or false")


def _validate_log_level(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("log level must be a string")

    normalized = value.strip().upper()

    if normalized not in VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ConfigurationError(f"log level must be one of: {allowed}")

    return normalized


def _validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigurationError("Ollama timeout must be a number")

    timeout = float(value)

    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigurationError("Ollama timeout must be finite and greater than zero")

    return timeout


def _validate_optional_model(value: object) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ConfigurationError("Ollama model must be a string when configured")

    model = value.strip()

    if not model:
        raise ConfigurationError("Ollama model must not be empty when configured")

    return model


def _validate_context_length(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError("Ollama context length must be a positive integer")

    return value


def _validate_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigurationError(f"{field_name} must be a non-negative integer")

    return value


def _validate_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{field_name} must be a positive integer")

    return value


def _validate_thinking(value: object) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError("Ollama thinking must be a boolean")

    return value


def _validate_keep_alive(value: object) -> str:
    if not isinstance(value, str) or _KEEP_ALIVE_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Ollama keep-alive must be 0 or a positive duration using ms, s, m, or h"
        )

    return value


def _validate_loopback_url(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Ollama base URL must be a non-empty string")

    if not value.strip():
        raise ConfigurationError("Ollama base URL must be a non-empty string")

    if any(character.isspace() for character in value):
        raise ConfigurationError("Ollama base URL must not contain whitespace")

    if "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ConfigurationError("Ollama base URL contains an invalid character")

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ConfigurationError("Ollama base URL is invalid") from None

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ConfigurationError("Ollama base URL must use HTTP or HTTPS")

    if not parsed.hostname:
        raise ConfigurationError("Ollama base URL must include a host")

    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError("Ollama base URL must not contain credentials")

    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError("Ollama base URL contains an invalid port")

    if parsed.query or parsed.fragment:
        raise ConfigurationError("Ollama base URL must not contain a query or fragment")

    if parsed.path not in {"", "/"}:
        raise ConfigurationError("Ollama base URL must not contain a path")

    if not _is_loopback_host(parsed.hostname):
        raise ConfigurationError("Ollama base URL host must be a loopback address")

    if "%" in parsed.hostname:
        raise ConfigurationError("Ollama base URL must not contain an IPv6 scope identifier")

    if parsed.hostname.lower() == "localhost":
        port_suffix = f":{port}" if port is not None else ""
        return f"{parsed.scheme.lower()}://127.0.0.1{port_suffix}"

    return value.rstrip("/")


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True

    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
