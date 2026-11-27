"""Network-free tests for CLI arguments, lifecycle, conversation, and tools."""

import argparse
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from io import StringIO

import pytest

from kosmos.cli.main import APPROVED_TOOLS, build_parser, main, run_cli
from kosmos.core.config import DEFAULT_OLLAMA_MODEL
from kosmos.core.exceptions import InvalidProviderResponseError, ProviderUnavailableError
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
)
from kosmos.intelligence.providers.ollama import OllamaModel
from kosmos.intelligence.tools import (
    ToolCall,
    ToolInferenceRequest,
    ToolInferenceResponse,
)


@dataclass(slots=True)
class FakeRuntimeProvider:
    models: tuple[OllamaModel, ...] = ()
    version: str = "0.12.0"
    chunks: tuple[InferenceChunk, ...] = ()
    tool_responses: list[ToolInferenceResponse | Exception] = field(default_factory=list)
    startup_error: Exception | None = None
    text_requests: list[InferenceRequest] = field(default_factory=list)
    tool_requests: list[ToolInferenceRequest] = field(default_factory=list)
    closed: bool = False

    async def __aenter__(self) -> "FakeRuntimeProvider":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True

    async def get_version(self) -> str:
        if self.startup_error is not None:
            raise self.startup_error
        return self.version

    async def list_models(self) -> tuple[OllamaModel, ...]:
        return self.models

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.text_requests.append(request)
        return InferenceResponse(request.model, "Complete response")

    async def generate_with_tools(self, request: ToolInferenceRequest) -> ToolInferenceResponse:
        self.tool_requests.append(request)
        response = self.tool_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.text_requests.append(request)
        for chunk in self.chunks:
            yield chunk


def _model(name: str = DEFAULT_OLLAMA_MODEL) -> OllamaModel:
    return OllamaModel(name, name, "2026-11-01T00:00:00Z", 1, "digest")


def _arguments(*values: str) -> argparse.Namespace:
    return build_parser().parse_args(values)


def _input_reader(*values: str):
    remaining = iter(values)
    return lambda _: next(remaining)


def _run(
    provider: FakeRuntimeProvider,
    arguments: argparse.Namespace,
    *inputs: str,
    environment: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    output = StringIO()
    error = StringIO()
    code = asyncio.run(
        run_cli(
            arguments,
            environment={} if environment is None else environment,
            provider_factory=lambda _: provider,  # type: ignore[arg-type,return-value]
            input_reader=_input_reader(*inputs),
            output=output,
            error_output=error,
        )
    )
    return code, output.getvalue(), error.getvalue()


def test_help_exits_without_initializing_provider(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--help"])

    assert stopped.value.code == 0
    assert "--list-models" in capsys.readouterr().out


def test_version_exits_without_initializing_provider(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--version"])

    assert stopped.value.code == 0
    assert capsys.readouterr().out.startswith("Kosmos 0.1.0")


def test_default_effort_is_low() -> None:
    assert _arguments().effort == "low"


@pytest.mark.parametrize("level", ["instant", "low", "medium", "high"])
def test_supported_effort_arguments(level: str) -> None:
    assert _arguments("--effort", level).effort == level


@pytest.mark.parametrize("level", ["expert", "auto", "invalid"])
def test_rejects_unsupported_effort_arguments(level: str) -> None:
    with pytest.raises(SystemExit) as stopped:
        _arguments("--effort", level)

    assert stopped.value.code == 2


def test_list_models_prints_local_models_and_closes_provider() -> None:
    provider = FakeRuntimeProvider(models=(_model(), _model("another:latest")))

    code, output, error = _run(provider, _arguments("--list-models"))

    assert code == 0
    assert DEFAULT_OLLAMA_MODEL in output
    assert "another:latest" in output
    assert error == ""
    assert provider.closed is True


def test_list_models_accepts_an_empty_installation() -> None:
    provider = FakeRuntimeProvider()

    code, output, _ = _run(provider, _arguments("--list-models"))

    assert code == 0
    assert "No models are installed" in output


def test_missing_selected_model_is_reported_without_inference() -> None:
    provider = FakeRuntimeProvider(models=(_model("different:model"),))

    code, _, error = _run(provider, _arguments("--model", "wanted:model"))

    assert code == 1
    assert "wanted:model" in error
    assert "ollama pull wanted:model" in error
    assert provider.text_requests == []
    assert provider.closed is True


def test_empty_model_list_is_reported_without_inference() -> None:
    provider = FakeRuntimeProvider()

    code, _, error = _run(provider, _arguments())

    assert code == 1
    assert "No models are installed" in error
    assert provider.closed is True


def test_explicit_model_overrides_environment_model() -> None:
    provider = FakeRuntimeProvider(models=(_model("argument:model"),))

    code, output, _ = _run(
        provider,
        _arguments("--model", "argument:model"),
        "/exit",
        environment={"KOSMOS_OLLAMA_MODEL": "environment:model"},
    )

    assert code == 0
    assert "Model:          argument:model" in output


def test_environment_model_overrides_official_default() -> None:
    provider = FakeRuntimeProvider(models=(_model("environment:model"),))

    code, output, _ = _run(
        provider,
        _arguments(),
        "/exit",
        environment={"KOSMOS_OLLAMA_MODEL": "environment:model"},
    )

    assert code == 0
    assert "Model:          environment:model" in output


def test_official_model_is_used_as_final_fallback() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    code, output, _ = _run(provider, _arguments(), "/exit")

    assert code == 0
    assert f"Model:          {DEFAULT_OLLAMA_MODEL}" in output


def test_startup_greeting_is_deterministic_and_does_not_run_inference() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    code, output, error = _run(provider, _arguments(), "/exit")

    assert code == 0
    assert "Kosmos: À sua disposição, senhor." in output
    assert "Offline verified" not in output
    assert provider.text_requests == []
    assert provider.tool_requests == []
    assert error == ""


def test_provider_unavailable_is_clear_and_provider_is_closed() -> None:
    provider = FakeRuntimeProvider(startup_error=ProviderUnavailableError("unavailable"))

    code, _, error = _run(provider, _arguments())

    assert code == 1
    assert "local Ollama service is unavailable" in error
    assert provider.closed is True


def test_instant_turn_streams_unicode_and_preserves_whitespace() -> None:
    provider = FakeRuntimeProvider(
        models=(_model(),),
        chunks=(
            InferenceChunk(DEFAULT_OLLAMA_MODEL, "Olá, "),
            InferenceChunk(DEFAULT_OLLAMA_MODEL, "senhor.\nTudo bem?", True),
        ),
    )

    code, output, error = _run(
        provider,
        _arguments("--effort", "instant"),
        "Bom dia",
        "/exit",
    )

    assert code == 0
    assert "Kosmos: Olá, senhor.\nTudo bem?" in output
    assert error == ""
    assert len(provider.text_requests) == 1
    assert provider.text_requests[0].thinking is False


def test_cli_propagates_conversation_history_configuration() -> None:
    provider = FakeRuntimeProvider(
        models=(_model(),),
        chunks=(InferenceChunk(DEFAULT_OLLAMA_MODEL, "response", True),),
    )

    code, _, error = _run(
        provider,
        _arguments("--effort", "instant"),
        "first private turn",
        "second turn",
        "/exit",
        environment={"KOSMOS_CONVERSATION_MAX_HISTORY_TURNS": "0"},
    )

    assert code == 0
    assert error == ""
    assert len(provider.text_requests) == 2
    assert len(provider.text_requests[1].messages) == 2
    assert all(
        "first private turn" not in message.content
        for message in provider.text_requests[1].messages
    )


def test_no_tools_uses_streaming_and_does_not_advertise_tools() -> None:
    provider = FakeRuntimeProvider(
        models=(_model(),),
        chunks=(InferenceChunk(DEFAULT_OLLAMA_MODEL, "Safe response", True),),
    )

    code, output, _ = _run(
        provider,
        _arguments("--no-tools"),
        "/tools",
        "hello",
        "/exit",
    )

    assert code == 0
    assert (
        "calculate: Use for one requested deterministic addition, subtraction, multiplication, "
        "or division; not for conceptual explanations or expression evaluation. "
        "(registered, disabled)" in output
    )
    assert len(provider.text_requests) == 1
    assert provider.tool_requests == []


def test_calculate_is_explicitly_authorized_and_executed() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    provider = FakeRuntimeProvider(
        models=(_model(),),
        tool_responses=[
            ToolInferenceResponse(DEFAULT_OLLAMA_MODEL, "", (call,)),
            ToolInferenceResponse(DEFAULT_OLLAMA_MODEL, "The result is 4000.", ()),
        ],
    )

    code, output, _ = _run(provider, _arguments(), "calculate", "/exit")

    assert code == 0
    assert "[calculate: success]\nResult: 4000" in output
    assert "Kosmos: The result is 4000." in output
    assert tuple(tool.name for tool in provider.tool_requests[0].tools) == APPROVED_TOOLS
    assert '"result":4000' in provider.tool_requests[1].messages[-1].content


def test_status_reports_verified_and_configured_values_without_inference() -> None:
    provider = FakeRuntimeProvider(models=(_model(),), version="0.12.3")

    code, output, error = _run(
        provider,
        _arguments(),
        "/status",
        "/exit",
        environment={
            "KOSMOS_OLLAMA_CONTEXT_LENGTH": "4096",
            "KOSMOS_CONVERSATION_MAX_HISTORY_TURNS": "7",
            "KOSMOS_CONVERSATION_MAX_CONTEXT_CHARACTERS": "8000",
        },
    )

    assert code == 0
    assert "Provider version: 0.12.3 (verified)" in output
    assert "Model: qwen3.5:4b-q4_K_M (selected)" in output
    assert "Provider context window: 4096 tokens (configured)" in output
    assert "Conversation history limit: 7 turns (configured)" in output
    assert "Orchestration character budget: 12000 characters (configured)" in output
    assert "Response reserve: 2000 characters (configured)" in output
    assert provider.text_requests == []
    assert provider.tool_requests == []
    assert error == ""


def test_stream_metrics_include_context_and_first_visible_text() -> None:
    metrics = InferenceMetrics(
        prompt_eval_count=10,
        eval_count=4,
        eval_duration_ns=1_000_000_000,
    )
    provider = FakeRuntimeProvider(
        models=(_model(),),
        chunks=(
            InferenceChunk(DEFAULT_OLLAMA_MODEL, ""),
            InferenceChunk(DEFAULT_OLLAMA_MODEL, "Visible", True, metrics),
        ),
    )

    code, output, error = _run(
        provider,
        _arguments("--effort", "instant", "--metrics"),
        "hello",
        "/exit",
    )

    assert code == 0
    assert "Time to first visible text:" in output
    assert "Context" in output
    assert "History selected: 0/0 turns" in output
    assert "Final provider request (text)" in output
    assert "Serialized input:" in output
    assert "Provider context: 4096 configured tokens" in output
    assert error == ""


def test_interrupted_stream_marks_partial_text_and_keeps_session_usable() -> None:
    provider = FakeRuntimeProvider(
        models=(_model(),),
        chunks=(InferenceChunk(DEFAULT_OLLAMA_MODEL, "Partial response"),),
    )

    code, output, error = _run(
        provider,
        _arguments("--effort", "instant", "--metrics"),
        "hello",
        "/exit",
    )

    assert code == 0
    assert "Kosmos: Partial response" in output
    assert "Response interrupted; partial content was not committed." in output
    assert "Metrics\n" not in output
    assert "invalid response" in error
    assert "Kosmos stopped." in output


def test_tool_evidence_survives_failure_of_final_response() -> None:
    call = ToolCall(
        "call_1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    provider = FakeRuntimeProvider(
        models=(_model(),),
        tool_responses=[
            ToolInferenceResponse(DEFAULT_OLLAMA_MODEL, "", (call,)),
            InvalidProviderResponseError("invalid final response"),
        ],
    )

    code, output, error = _run(provider, _arguments(), "calculate", "/exit")

    assert code == 0
    assert "[calculate: success]\nResult: 4000" in output
    assert "Error: Ollama returned an invalid response." in output
    assert "Kosmos stopped." in output
    assert error == ""


def test_streaming_context_limit_returns_to_interaction_without_inference() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    code, output, error = _run(
        provider,
        _arguments("--effort", "instant"),
        "x" * 12_000,
        "/exit",
    )

    assert code == 0
    assert "exceeds the configured context budget" in error
    assert "Kosmos stopped." in output
    assert provider.text_requests == []


def test_count_items_is_explicitly_authorized_and_executed() -> None:
    call = ToolCall("call_1", "count_items", {"items": ["one", "two", "three"]})
    provider = FakeRuntimeProvider(
        models=(_model(),),
        tool_responses=[
            ToolInferenceResponse(DEFAULT_OLLAMA_MODEL, "", (call,)),
            ToolInferenceResponse(DEFAULT_OLLAMA_MODEL, "There are three items.", ()),
        ],
    )

    code, output, _ = _run(provider, _arguments(), "count", "/exit")

    assert code == 0
    assert "Kosmos: There are three items." in output
    assert '"count":3' in provider.tool_requests[1].messages[-1].content


def test_internal_commands_are_not_sent_to_provider_and_preserve_session() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    code, output, _ = _run(
        provider,
        _arguments(),
        "/help",
        "/status",
        "/effort medium",
        "/metrics on",
        "/tools",
        "/clear",
        "/exit",
    )

    assert code == 0
    assert "Commands" in output
    assert "Effort changed to medium." in output
    assert "Metrics on." in output
    assert "Conversation history cleared." in output
    assert provider.text_requests == []
    assert provider.tool_requests == []


def test_unknown_command_returns_to_prompt_without_inference() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    code, _, error = _run(provider, _arguments(), "/unknown", "/exit")

    assert code == 0
    assert "unknown command" in error
    assert provider.text_requests == []


def test_eof_closes_provider() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))
    output = StringIO()

    def end_of_input(_: str) -> str:
        raise EOFError

    code = asyncio.run(
        run_cli(
            _arguments(),
            environment={},
            provider_factory=lambda _: provider,  # type: ignore[arg-type,return-value]
            input_reader=end_of_input,
            output=output,
            error_output=StringIO(),
        )
    )

    assert code == 0
    assert "end of input" in output.getvalue()
    assert provider.closed is True


def test_invalid_configuration_does_not_create_provider() -> None:
    created = False

    def provider_factory(_: object) -> FakeRuntimeProvider:
        nonlocal created
        created = True
        return FakeRuntimeProvider()

    error = StringIO()
    code = asyncio.run(
        run_cli(
            _arguments(),
            environment={"KOSMOS_OLLAMA_TIMEOUT_SECONDS": "invalid"},
            provider_factory=provider_factory,  # type: ignore[arg-type]
            output=StringIO(),
            error_output=error,
        )
    )

    assert code == 1
    assert "Invalid configuration" in error.getvalue()
    assert created is False


def test_keyboard_interrupt_closes_provider() -> None:
    provider = FakeRuntimeProvider(models=(_model(),))

    def interrupt(_: str) -> str:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(
            run_cli(
                _arguments(),
                environment={},
                provider_factory=lambda _: provider,  # type: ignore[arg-type,return-value]
                input_reader=interrupt,
                output=StringIO(),
                error_output=StringIO(),
            )
        )

    assert provider.closed is True
