"""Benchmark CLI authorization and MockTransport integration tests."""

import asyncio
import io
import json

import httpx
import pytest

import kosmos.benchmarking.main as benchmark_module
from kosmos.benchmarking.main import EXIT_ERROR, EXIT_OK, EXIT_USAGE, build_parser, main, run_cli
from kosmos.benchmarking.models import ExecutionMode
from kosmos.core.config import DEFAULT_OLLAMA_MODEL
from kosmos.intelligence.providers.ollama import OllamaProvider


def test_execution_without_live_authorization_never_builds_a_provider(capsys) -> None:
    assert main(["--suite", "quick"]) == EXIT_USAGE
    assert "requires explicit --live" in capsys.readouterr().err


def test_help_and_scenario_listing_do_not_require_ollama(capsys) -> None:
    assert main(["--list-scenarios"]) == EXIT_OK
    output = capsys.readouterr().out

    assert "identity" in output
    assert "streaming_instant" in output


def test_real_entrypoint_declares_live_provenance_independently_from_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = None

    async def fake_run_cli(arguments, *, execution_mode):
        nonlocal observed
        observed = execution_mode
        return EXIT_OK

    monkeypatch.setattr(benchmark_module, "run_cli", fake_run_cli)

    assert benchmark_module.main(["--live"]) == EXIT_OK
    assert observed is ExecutionMode.LIVE


def test_quick_suite_runs_with_mock_transport_and_closes_provider() -> None:
    providers: list[OllamaProvider] = []
    chat_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test-ollama"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": DEFAULT_OLLAMA_MODEL,
                            "model": DEFAULT_OLLAMA_MODEL,
                            "modified_at": "2026-01-01T00:00:00Z",
                            "size": 1,
                            "digest": "test-digest",
                        }
                    ]
                },
            )

        payload = json.loads(request.content)
        chat_payloads.append(payload)
        messages = payload["messages"]
        last = messages[-1]
        if last["role"] == "tool":
            tool_payload = json.loads(last["content"])
            value = tool_payload["data"].get("result", tool_payload["data"].get("count"))
            return _chat_document(f"O resultado é {value}.")
        if payload.get("tools"):
            prompt = last["content"]
            if "125" in prompt:
                function = {
                    "name": "calculate",
                    "arguments": {"operation": "multiply", "a": 125, "b": 32},
                }
            else:
                function = {
                    "name": "count_items",
                    "arguments": {"items": ["Java", "Python", "Go", "Rust", "Kotlin"]},
                }
            return _chat_document("", tool_calls=[{"function": function}])
        if "linguagem" in last["content"].casefold():
            return _chat_document("Você mencionou Java 21.")
        return _chat_document("Resposta fictícia para revisão.")

    def factory(settings):
        provider = OllamaProvider(settings, transport=httpx.MockTransport(handler))
        providers.append(provider)
        return provider

    arguments = build_parser().parse_args(["--suite", "quick", "--live"])
    output = io.StringIO()
    errors = io.StringIO()
    exit_code = asyncio.run(
        run_cli(
            arguments,
            execution_mode=ExecutionMode.SIMULATED,
            environment={"KOSMOS_CONVERSATION_MAX_HISTORY_TURNS": "0"},
            provider_factory=factory,
            output=output,
            error_output=errors,
        )
    )

    assert exit_code == EXIT_OK
    assert errors.getvalue() == ""
    assert "Execution: SIMULATED" in output.getvalue()
    assert "Validation: PENDING MAINTAINER REVIEW" in output.getvalue()
    assert providers[0].is_closed is True
    recall_request = next(
        payload
        for payload in chat_payloads
        if "linguagem" in payload["messages"][-1]["content"].casefold()
    )
    assert len(recall_request["messages"]) == 2


def test_initialization_failure_is_reported_and_provider_is_closed() -> None:
    providers: list[OllamaProvider] = []

    def factory(settings):
        provider = OllamaProvider(
            settings,
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        )
        providers.append(provider)
        return provider

    arguments = build_parser().parse_args(["--live"])
    errors = io.StringIO()
    exit_code = asyncio.run(
        run_cli(
            arguments,
            execution_mode=ExecutionMode.SIMULATED,
            environment={},
            provider_factory=factory,
            output=io.StringIO(),
            error_output=errors,
        )
    )

    assert exit_code == EXIT_ERROR
    assert "HTTP 500" in errors.getvalue()
    assert providers[0].is_closed is True


def _chat_document(content: str, *, tool_calls=None) -> httpx.Response:
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return httpx.Response(
        200,
        json={
            "model": DEFAULT_OLLAMA_MODEL,
            "message": message,
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 4,
            "eval_duration": 100_000_000,
        },
    )
