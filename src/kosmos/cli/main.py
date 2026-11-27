"""Synchronous entry point and asynchronous lifecycle for the development CLI."""

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import Protocol
from uuid import UUID

from kosmos.cli.commands import (
    CommandError,
    CommandName,
    LocalCommand,
    parse_local_command,
    supported_effort_levels,
)
from kosmos.cli.rendering import (
    StreamSanitizer,
    render_banner,
    render_execution_evidence,
    render_metrics,
    render_result_error,
    render_stream_metrics,
    render_tools,
    sanitize_terminal_text,
)
from kosmos.core.config import DEFAULT_OLLAMA_MODEL, ApplicationSettings, load_settings
from kosmos.core.exceptions import (
    ConfigurationError,
    ContextLimitExceededError,
    InferenceError,
    InvalidProviderResponseError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ToolCapabilityUnavailableError,
)
from kosmos.core.orchestration import (
    CoreOrchestrator,
    EffortLevel,
    EffortPolicy,
    OrchestrationContextPolicy,
    OrchestrationStatus,
    default_effort_policies,
)
from kosmos.intelligence.conversation import ContextPolicy
from kosmos.intelligence.providers.ollama import OllamaModel, OllamaProvider
from kosmos.intelligence.tools import ToolAuthorization, ToolRegistry, create_builtin_registry

APPROVED_TOOLS = ("calculate", "count_items")
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130


class Output(Protocol):
    """Minimal output boundary used by the terminal and deterministic tests."""

    def write(self, content: str) -> object: ...

    def flush(self) -> object: ...


ProviderFactory = Callable[[ApplicationSettings], OllamaProvider]
InputReader = Callable[[str], str]


@dataclass(slots=True)
class CliState:
    """Mutable presentation preferences for one conversation session."""

    effort: EffortLevel
    metrics_enabled: bool
    tools_enabled: bool


@dataclass(frozen=True, slots=True)
class RuntimeDetails:
    """Verified and configured values retained for local status rendering."""

    kosmos_version: str
    provider_version: str
    model: str
    session_id: UUID
    settings: ApplicationSettings
    orchestration_context: OrchestrationContextPolicy


def build_parser() -> argparse.ArgumentParser:
    """Build the side-effect-free command-line parser."""

    parser = argparse.ArgumentParser(
        prog="kosmos",
        description="Run the local Kosmos development conversation interface.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Kosmos {version('kosmos')}",
    )
    parser.add_argument(
        "--effort",
        choices=[level.value for level in supported_effort_levels()],
        default=EffortLevel.LOW.value,
        help="effort level for conversation turns (default: low)",
    )
    parser.add_argument("--metrics", action="store_true", help="show operational turn metrics")
    parser.add_argument("--no-tools", action="store_true", help="disable all tool availability")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="list models installed in local Ollama and exit",
    )
    parser.add_argument("--model", help="explicit installed Ollama model identifier")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and own the top-level asyncio lifecycle."""

    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(run_cli(arguments))
    except KeyboardInterrupt:
        print("\nKosmos stopped by user.", file=sys.stderr)
        return EXIT_INTERRUPTED


async def run_cli(
    arguments: argparse.Namespace,
    *,
    environment: dict[str, str] | None = None,
    provider_factory: ProviderFactory = OllamaProvider,
    input_reader: InputReader = input,
    output: Output = sys.stdout,
    error_output: Output = sys.stderr,
) -> int:
    """Run startup validation and the optional interactive conversation."""

    try:
        settings = load_settings(os.environ if environment is None else environment)
        model = arguments.model or settings.ollama_model or DEFAULT_OLLAMA_MODEL
        provider = provider_factory(settings)
    except (ConfigurationError, TypeError, ValueError) as error:
        _write_line(error_output, f"Error: Invalid configuration: {error}")
        return EXIT_ERROR

    try:
        async with provider:
            ollama_version = await provider.get_version()
            models = await provider.list_models()

            if arguments.list_models:
                _render_model_list(models, output)
                return EXIT_OK

            if not models:
                _write_line(error_output, "Error: No models are installed in local Ollama.")
                _write_line(error_output, "Install the configured model manually, then retry.")
                return EXIT_ERROR

            if not _model_is_installed(model, models):
                safe_model = sanitize_terminal_text(model)
                _write_line(
                    error_output, f"Error: The configured model is not installed: {safe_model}"
                )
                _write_line(error_output, f"Install it manually with: ollama pull {safe_model}")
                return EXIT_ERROR

            registry = create_builtin_registry()
            context_policy = ContextPolicy(
                max_history_turns=settings.conversation_max_history_turns,
                max_context_characters=settings.conversation_max_context_characters,
            )
            orchestration_context = OrchestrationContextPolicy()
            orchestrator = CoreOrchestrator(
                provider,
                tool_registry=registry,
                context_policy=context_policy,
                orchestration_context_policy=orchestration_context,
            )
            session = orchestrator.create_session()
            state = CliState(
                effort=EffortLevel(arguments.effort),
                metrics_enabled=arguments.metrics,
                tools_enabled=not arguments.no_tools,
            )
            runtime = RuntimeDetails(
                kosmos_version=version("kosmos"),
                provider_version=ollama_version,
                model=model,
                session_id=session.session_id,
                settings=settings,
                orchestration_context=orchestration_context,
            )
            _write_line(
                output,
                render_banner(
                    version=runtime.kosmos_version,
                    ollama_version=ollama_version,
                    model=model,
                    effort=state.effort.value,
                    thinking=_policy(state.effort).thinking,
                    tool_names=_effective_tool_names(state),
                ),
            )
            try:
                await _conversation_loop(
                    orchestrator,
                    registry,
                    runtime,
                    state,
                    input_reader,
                    output,
                    error_output,
                )
            finally:
                orchestrator.delete_session(session.session_id)

            return EXIT_OK
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        raise
    except ProviderUnavailableError:
        _write_line(error_output, "Error: The local Ollama service is unavailable.")
        _write_line(error_output, "Ensure Ollama is installed and running, then restart Kosmos.")
    except ProviderTimeoutError:
        _write_line(error_output, "Error: The local Ollama request timed out.")
    except ProviderHTTPError as error:
        _write_line(error_output, f"Error: Ollama returned HTTP status {error.status_code}.")
    except InvalidProviderResponseError:
        _write_line(error_output, "Error: Ollama returned an invalid response.")
    except InferenceError:
        _write_line(error_output, "Error: Ollama could not complete the request.")

    return EXIT_ERROR


async def _conversation_loop(
    orchestrator: CoreOrchestrator,
    registry: ToolRegistry,
    runtime: RuntimeDetails,
    state: CliState,
    input_reader: InputReader,
    output: Output,
    error_output: Output,
) -> None:
    while True:
        try:
            content = input_reader("\nYou: ")
        except EOFError:
            _write_line(output, "\nKosmos stopped at end of input.")
            return

        if not content.strip():
            continue

        try:
            command = parse_local_command(content)
        except CommandError as error:
            _write_line(error_output, f"Error: {error}")
            continue

        if command is not None:
            should_exit = _handle_command(command, orchestrator, registry, runtime, state, output)
            if should_exit:
                return
            continue

        try:
            await _run_turn(
                orchestrator,
                runtime.session_id,
                runtime.model,
                content,
                state,
                output,
                runtime.settings.ollama_context_length,
            )
        except (ProviderTimeoutError, TimeoutError):
            _write_line(error_output, "Error: The request timed out.")
        except ProviderUnavailableError:
            _write_line(error_output, "Error: The local Ollama service is unavailable.")
        except ProviderHTTPError as error:
            _write_line(error_output, f"Error: Ollama returned HTTP status {error.status_code}.")
        except InvalidProviderResponseError:
            _write_line(error_output, "Error: Ollama returned an invalid response.")
        except ContextLimitExceededError:
            _write_line(
                error_output,
                "Error: The request exceeds the configured context budget. "
                "Try a shorter message or clear the conversation.",
            )
        except InferenceError:
            _write_line(error_output, "Error: Ollama could not complete the inference.")
        except ToolCapabilityUnavailableError:
            _write_line(error_output, "Error: Tool calling is unavailable for this provider.")


async def _run_turn(
    orchestrator: CoreOrchestrator,
    session_id: UUID,
    model: str,
    content: str,
    state: CliState,
    output: Output,
    provider_context_tokens: int,
) -> None:
    authorization, selected_tools = _tool_access(state)
    if not selected_tools:
        await _run_streaming_turn(
            orchestrator,
            session_id,
            model,
            content,
            state,
            authorization,
            output,
            provider_context_tokens,
        )
        return

    result = await orchestrator.generate(
        session_id,
        content,
        model=model,
        effort=state.effort,
        authorization=authorization,
        selected_tools=selected_tools,
    )
    evidence = render_execution_evidence(result)
    if evidence:
        _write_line(output, evidence)
        _write_line(output, "")

    if result.status is OrchestrationStatus.COMPLETED:
        _write_line(output, f"Kosmos: {sanitize_terminal_text(result.content or '')}")
    else:
        _write_line(output, render_result_error(result))

    if state.metrics_enabled:
        _write_line(
            output,
            f"\n{render_metrics(result.metrics, provider_context_tokens=provider_context_tokens)}",
        )


async def _run_streaming_turn(
    orchestrator: CoreOrchestrator,
    session_id: UUID,
    model: str,
    content: str,
    state: CliState,
    authorization: ToolAuthorization,
    output: Output,
    provider_context_tokens: int,
) -> None:
    stream = orchestrator.stream(
        session_id,
        content,
        model=model,
        effort=state.effort,
        authorization=authorization,
        selected_tools=(),
    )
    sanitizer = StreamSanitizer()
    started_at = time.monotonic()
    final_metrics = None
    time_to_first_visible_text = None
    content_emitted = False
    completed = False
    output.write("Kosmos: ")
    output.flush()

    try:
        async for chunk in stream:
            safe_content = sanitizer.feed(chunk.content)
            output.write(safe_content)
            output.flush()
            content_emitted = content_emitted or bool(safe_content)
            if time_to_first_visible_text is None and any(
                not character.isspace() for character in safe_content
            ):
                time_to_first_visible_text = time.monotonic() - started_at
            if chunk.done:
                final_metrics = chunk.metrics
                completed = True
    finally:
        sanitizer.finish()
        await stream.aclose()
        if content_emitted and not completed:
            _write_line(output, "\nResponse interrupted; partial content was not committed.")

    _write_line(output, "")
    if state.metrics_enabled and completed:
        elapsed = time.monotonic() - started_at
        _write_line(
            output,
            "\n"
            + render_stream_metrics(
                effort=state.effort.value,
                thinking=_policy(state.effort).thinking,
                elapsed_seconds=elapsed,
                inference=final_metrics,
                context=stream.context_metrics,
                time_to_first_visible_text=time_to_first_visible_text,
                provider_context_tokens=provider_context_tokens,
            ),
        )


def _handle_command(
    command: LocalCommand,
    orchestrator: CoreOrchestrator,
    registry: ToolRegistry,
    runtime: RuntimeDetails,
    state: CliState,
    output: Output,
) -> bool:
    if command.name is CommandName.EXIT:
        _write_line(output, "Kosmos stopped.")
        return True
    if command.name is CommandName.HELP:
        _write_line(output, _command_help())
    elif command.name is CommandName.STATUS:
        _write_line(output, _status(runtime, state))
    elif command.name is CommandName.TOOLS:
        authorized, _ = _tool_access(state)
        _write_line(output, render_tools(registry.definitions(), authorized.allowed_tools))
    elif command.name is CommandName.CLEAR:
        orchestrator.clear_session(runtime.session_id)
        _write_line(output, "Conversation history cleared.")
    elif command.name is CommandName.EFFORT:
        if command.value is None:
            supported = ", ".join(level.value for level in supported_effort_levels())
            _write_line(output, f"Current effort: {state.effort.value}. Supported: {supported}.")
        else:
            state.effort = EffortLevel(command.value)
            _write_line(output, f"Effort changed to {state.effort.value}.")
    elif command.name is CommandName.METRICS:
        state.metrics_enabled = (
            not state.metrics_enabled if command.value is None else command.value == "on"
        )
        _write_line(output, f"Metrics {_on_off(state.metrics_enabled)}.")

    return False


def _tool_access(state: CliState) -> tuple[ToolAuthorization, tuple[str, ...]]:
    if not state.tools_enabled or not _policy(state.effort).tools_enabled:
        return ToolAuthorization(), ()
    return ToolAuthorization(APPROVED_TOOLS), APPROVED_TOOLS


def _effective_tool_names(state: CliState) -> tuple[str, ...]:
    return _tool_access(state)[1]


def _policy(effort: EffortLevel) -> EffortPolicy:
    return default_effort_policies()[effort]


def _model_is_installed(model: str, models: Sequence[OllamaModel]) -> bool:
    return any(model in {installed.name, installed.model} for installed in models)


def _render_model_list(models: Sequence[OllamaModel], output: Output) -> None:
    if not models:
        _write_line(output, "No models are installed in local Ollama.")
        return

    _write_line(output, "Installed Ollama models:")
    for model in models:
        _write_line(output, f"  {sanitize_terminal_text(model.name)}")


def _status(runtime: RuntimeDetails, state: CliState) -> str:
    policy = _policy(state.effort)
    tools = ", ".join(_effective_tool_names(state)) or "Disabled"
    settings = runtime.settings
    orchestration = runtime.orchestration_context
    input_budget = orchestration.max_context_characters - orchestration.response_reserve_characters
    return (
        "Status\n"
        f"  Kosmos version: {sanitize_terminal_text(runtime.kosmos_version)}\n"
        "  Provider: Ollama\n"
        f"  Provider version: {sanitize_terminal_text(runtime.provider_version)} (verified)\n"
        "  Connection: Local loopback (verified at startup)\n"
        f"  Model: {sanitize_terminal_text(runtime.model)} (selected)\n"
        f"  Session: {runtime.session_id}\n"
        f"  Effort: {state.effort.value.upper()}\n"
        f"  Thinking: {'Enabled' if policy.thinking else 'Disabled'}\n"
        f"  Effective tools: {tools}\n"
        f"  Metrics: {_on_off(state.metrics_enabled).capitalize()}\n"
        f"  Provider context window: {settings.ollama_context_length} tokens (configured)\n"
        "  Conversation history limit: "
        f"{settings.conversation_max_history_turns} turns (configured)\n"
        "  Conversation character budget: "
        f"{settings.conversation_max_context_characters} characters (configured)\n"
        "  Orchestration character budget: "
        f"{orchestration.max_context_characters} characters (configured)\n"
        f"  Integrated input budget: {input_budget} characters (configured)\n"
        "  Response reserve: "
        f"{orchestration.response_reserve_characters} characters (configured)"
    )


def _command_help() -> str:
    return (
        "Commands\n"
        "  /help             Show this help.\n"
        "  /status           Show current session configuration.\n"
        "  /effort [level]   Show or change effort.\n"
        "  /metrics [on|off] Toggle or set metrics display.\n"
        "  /tools            Show effective tools and authorization.\n"
        "  /clear            Clear conversation history.\n"
        "  /exit             Close Kosmos safely."
    )


def _on_off(value: bool) -> str:
    return "on" if value else "off"


def _write_line(output: Output, content: str) -> None:
    output.write(content + "\n")
    output.flush()


if __name__ == "__main__":
    raise SystemExit(main())
