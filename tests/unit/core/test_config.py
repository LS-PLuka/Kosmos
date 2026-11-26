"""Behavioral tests for application configuration."""

import os
from dataclasses import FrozenInstanceError

import pytest

from kosmos.core.config import ApplicationSettings, load_settings
from kosmos.core.exceptions import ConfigurationError


def test_loads_defaults_without_selecting_a_model() -> None:
    settings = load_settings({})

    assert settings == ApplicationSettings()
    assert settings.log_level == "INFO"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_timeout_seconds == 120.0
    assert settings.ollama_model is None
    assert settings.ollama_context_length == 4096
    assert settings.ollama_thinking is False
    assert settings.ollama_keep_alive == "5m"


def test_environment_values_override_defaults() -> None:
    settings = load_settings(
        {
            "KOSMOS_LOG_LEVEL": "debug",
            "KOSMOS_OLLAMA_BASE_URL": "http://localhost:9999",
            "KOSMOS_OLLAMA_TIMEOUT_SECONDS": "2.5",
            "KOSMOS_OLLAMA_MODEL": "test-model",
            "KOSMOS_OLLAMA_CONTEXT_LENGTH": "8192",
            "KOSMOS_OLLAMA_THINKING": "TRUE",
            "KOSMOS_OLLAMA_KEEP_ALIVE": "30s",
        }
    )

    assert settings.log_level == "DEBUG"
    assert settings.ollama_base_url == "http://127.0.0.1:9999"
    assert settings.ollama_timeout_seconds == 2.5
    assert settings.ollama_model == "test-model"
    assert settings.ollama_context_length == 8192
    assert settings.ollama_thinking is True
    assert settings.ollama_keep_alive == "30s"


@pytest.mark.parametrize("level", ["TRACE", "", "verbose"])
def test_rejects_invalid_log_levels(level: str) -> None:
    with pytest.raises(ConfigurationError, match="log level"):
        load_settings({"KOSMOS_LOG_LEVEL": level})


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "not-a-number"])
def test_rejects_invalid_timeouts(timeout: str) -> None:
    with pytest.raises(ConfigurationError, match=r"TIMEOUT|timeout"):
        load_settings({"KOSMOS_OLLAMA_TIMEOUT_SECONDS": timeout})


@pytest.mark.parametrize(
    "url",
    [
        "ftp://127.0.0.1:11434",
        "http://example.com:11434",
        "http://192.168.1.20:11434",
        "http://user:example@localhost:11434",
        "http://@localhost:11434",
        "http://localhost:11434?option=value",
        "http://localhost:11434#fragment",
        "http://localhost:11434/api",
        "http://localhost:11434\\@example.com",
        "http://[::1%25loopback]:11434",
        "http://127.0.0.1:11434//example.com",
        "http://localhost:0",
        "http://localhost:65536",
        "http://127.0.0.1.example:11434",
        "http://local\nhost:11434",
        "http://local\thost:11434",
        "http://[::1",
        "not-a-url",
    ],
)
def test_rejects_invalid_or_non_loopback_urls(url: str) -> None:
    with pytest.raises(ConfigurationError, match=r"URL|url|loopback|HTTP"):
        load_settings({"KOSMOS_OLLAMA_BASE_URL": url})


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.2:11434",
        "http://127.255.255.255:11434",
        "http://[::1]:11434",
    ],
)
def test_accepts_loopback_urls(url: str) -> None:
    settings = load_settings({"KOSMOS_OLLAMA_BASE_URL": url})

    assert settings.ollama_base_url == url


@pytest.mark.parametrize(
    ("url", "normalized"),
    [
        ("http://localhost:11434", "http://127.0.0.1:11434"),
        ("https://LOCALHOST:11434", "https://127.0.0.1:11434"),
    ],
)
def test_normalizes_localhost_to_a_literal_loopback(url: str, normalized: str) -> None:
    settings = load_settings({"KOSMOS_OLLAMA_BASE_URL": url})

    assert settings.ollama_base_url == normalized


def test_explicit_environment_does_not_read_or_modify_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KOSMOS_LOG_LEVEL", "ERROR")
    before = os.environ.copy()

    settings = load_settings({"KOSMOS_LOG_LEVEL": "DEBUG"})

    assert settings.log_level == "DEBUG"
    assert os.environ == before


def test_rejects_an_empty_configured_model() -> None:
    with pytest.raises(ConfigurationError, match="model"):
        load_settings({"KOSMOS_OLLAMA_MODEL": "  "})


@pytest.mark.parametrize("context_length", ["0", "-1", "1.5", "true", ""])
def test_rejects_invalid_context_lengths(context_length: str) -> None:
    with pytest.raises(ConfigurationError, match=r"CONTEXT_LENGTH|context length"):
        load_settings({"KOSMOS_OLLAMA_CONTEXT_LENGTH": context_length})


@pytest.mark.parametrize("thinking", ["1", "yes", "enabled", ""])
def test_rejects_implicit_thinking_values(thinking: str) -> None:
    with pytest.raises(ConfigurationError, match="THINKING"):
        load_settings({"KOSMOS_OLLAMA_THINKING": thinking})


@pytest.mark.parametrize("keep_alive", ["-1", "five minutes", "5", "5d", " 5m", "5m "])
def test_rejects_invalid_keep_alive_values(keep_alive: str) -> None:
    with pytest.raises(ConfigurationError, match="keep-alive"):
        load_settings({"KOSMOS_OLLAMA_KEEP_ALIVE": keep_alive})


def test_normalizes_a_trailing_base_url_slash() -> None:
    settings = load_settings({"KOSMOS_OLLAMA_BASE_URL": "http://localhost:11434/"})

    assert settings.ollama_base_url == "http://127.0.0.1:11434"


def test_settings_remain_immutable() -> None:
    settings = ApplicationSettings()

    with pytest.raises(FrozenInstanceError):
        settings.ollama_thinking = True  # type: ignore[misc]
