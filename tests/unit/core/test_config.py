"""Behavioral tests for application configuration."""

import os

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


def test_environment_values_override_defaults() -> None:
    settings = load_settings(
        {
            "KOSMOS_LOG_LEVEL": "debug",
            "KOSMOS_OLLAMA_BASE_URL": "http://localhost:9999/api",
            "KOSMOS_OLLAMA_TIMEOUT_SECONDS": "2.5",
            "KOSMOS_OLLAMA_MODEL": "test-model",
        }
    )

    assert settings.log_level == "DEBUG"
    assert settings.ollama_base_url == "http://localhost:9999/api"
    assert settings.ollama_timeout_seconds == 2.5
    assert settings.ollama_model == "test-model"


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
        "http://localhost:11434",
        "https://LOCALHOST:11434",
        "http://127.0.0.2:11434",
        "http://127.255.255.255:11434",
        "http://[::1]:11434",
    ],
)
def test_accepts_loopback_urls(url: str) -> None:
    settings = load_settings({"KOSMOS_OLLAMA_BASE_URL": url})

    assert settings.ollama_base_url == url


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
