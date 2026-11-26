"""Explicit, side-effect-free application configuration."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

from kosmos.core.exceptions import ConfigurationError

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """Validated settings used by the current application foundations."""

    log_level: str = "INFO"
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    ollama_model: str | None = None

    def __post_init__(self) -> None:
        log_level = _validate_log_level(self.log_level)
        base_url = _validate_loopback_url(self.ollama_base_url)
        timeout = _validate_timeout(self.ollama_timeout_seconds)
        model = _validate_optional_model(self.ollama_model)

        object.__setattr__(self, "log_level", log_level)
        object.__setattr__(self, "ollama_base_url", base_url)
        object.__setattr__(self, "ollama_timeout_seconds", timeout)
        object.__setattr__(self, "ollama_model", model)


def load_settings(environment: Mapping[str, str] | None = None) -> ApplicationSettings:
    """Load settings from an explicit mapping or a snapshot of the process environment."""

    values = dict(os.environ if environment is None else environment)

    timeout = _parse_timeout(
        values.get("KOSMOS_OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_OLLAMA_TIMEOUT_SECONDS))
    )

    return ApplicationSettings(
        log_level=values.get("KOSMOS_LOG_LEVEL", "INFO"),
        ollama_base_url=values.get("KOSMOS_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        ollama_timeout_seconds=timeout,
        ollama_model=values.get("KOSMOS_OLLAMA_MODEL"),
    )


def _parse_timeout(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ConfigurationError("KOSMOS_OLLAMA_TIMEOUT_SECONDS must be a number") from None


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


def _validate_loopback_url(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Ollama base URL must be a non-empty string")

    if not value.strip():
        raise ConfigurationError("Ollama base URL must be a non-empty string")

    if any(character.isspace() for character in value):
        raise ConfigurationError("Ollama base URL must not contain whitespace")

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

    if not _is_loopback_host(parsed.hostname):
        raise ConfigurationError("Ollama base URL host must be a loopback address")

    return value


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True

    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
