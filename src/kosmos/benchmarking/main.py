"""Explicit live-only command-line entry point for Stage 01.8 validation."""

import argparse
import asyncio
import platform
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

from kosmos.benchmarking.models import BenchmarkConfig, BenchmarkMetadata, ExecutionMode
from kosmos.benchmarking.reporting import export_reports, render_terminal
from kosmos.benchmarking.runner import run_benchmark
from kosmos.benchmarking.scenarios import SCENARIO_VERSION, list_scenarios, select_suite
from kosmos.core.config import DEFAULT_OLLAMA_MODEL, ApplicationSettings, load_settings
from kosmos.core.exceptions import KosmosError
from kosmos.core.orchestration import CoreOrchestrator, EffortLevel, default_effort_policies
from kosmos.intelligence.providers.ollama import OllamaModel, OllamaProvider
from kosmos.intelligence.tools import create_builtin_registry

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


class Output(Protocol):
    """Minimal output boundary for terminal and deterministic tests."""

    def write(self, content: str) -> object: ...

    def flush(self) -> object: ...


ProviderFactory = Callable[[ApplicationSettings], OllamaProvider]


def build_parser() -> argparse.ArgumentParser:
    """Build a parser with no provider initialization or inference side effects."""

    parser = argparse.ArgumentParser(
        prog="kosmos-benchmark",
        description="Evaluate the Kosmos Core Engine against a local model.",
    )
    parser.add_argument("--version", action="version", version=f"Kosmos {version('kosmos')}")
    parser.add_argument("--list-scenarios", action="store_true", help="list scenarios and exit")
    parser.add_argument(
        "--suite",
        choices=("quick", "full", "performance"),
        default="quick",
        help="scenario suite (default: quick)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="explicitly authorize local Ollama inference",
    )
    parser.add_argument("--model", help="explicit installed Ollama model identifier")
    parser.add_argument("--repetitions", type=_positive_integer, help="measured runs per scenario")
    parser.add_argument(
        "--warm-up-runs",
        type=_non_negative_integer,
        help="warm-up runs per scenario, excluded from primary statistics",
    )
    parser.add_argument(
        "--efforts",
        nargs="+",
        choices=("instant", "low", "medium", "high"),
        help="performance-suite effort levels to include",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="explicit output base path for new JSON and Markdown reports",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and own the benchmark asyncio lifecycle."""

    arguments = build_parser().parse_args(argv)
    if arguments.list_scenarios:
        print(render_scenario_list())
        return EXIT_OK
    if not arguments.live:
        print(
            "Error: benchmark inference requires explicit --live authorization.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        return asyncio.run(run_cli(arguments, execution_mode=ExecutionMode.LIVE))
    except KeyboardInterrupt:
        print("\nBenchmark stopped by user.", file=sys.stderr)
        return 130


async def run_cli(
    arguments: argparse.Namespace,
    *,
    execution_mode: ExecutionMode,
    environment: dict[str, str] | None = None,
    provider_factory: ProviderFactory = OllamaProvider,
    output: Output = sys.stdout,
    error_output: Output = sys.stderr,
) -> int:
    """Validate the local runtime, execute the suite, report, and close the provider."""

    try:
        settings = load_settings(environment)
        model = arguments.model or settings.ollama_model or DEFAULT_OLLAMA_MODEL
        repetitions = arguments.repetitions or (3 if arguments.suite == "full" else 1)
        warmups = arguments.warm_up_runs
        if warmups is None:
            warmups = 1 if arguments.suite == "performance" else 0
        efforts = (
            tuple(EffortLevel(value) for value in arguments.efforts) if arguments.efforts else None
        )
        scenarios = select_suite(arguments.suite, efforts=efforts)
        if not scenarios:
            _write_line(error_output, "Error: no scenarios match the selected effort levels.")
            return EXIT_USAGE

        config = BenchmarkConfig(arguments.suite, model, repetitions, warmups)
        async with provider_factory(settings) as provider:
            ollama_version = await provider.get_version()
            models = await provider.list_models()
            installed = _find_model(model, models)
            if installed is None:
                _write_line(error_output, f"Error: model is not installed in local Ollama: {model}")
                return EXIT_ERROR

            metadata = _metadata(
                config,
                settings,
                installed.digest,
                ollama_version,
                execution_mode,
            )
            orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
            run = await run_benchmark(orchestrator, scenarios, config, metadata)

        _write_line(output, render_terminal(run))
        if arguments.output is not None:
            json_path, markdown_path = export_reports(run, arguments.output)
            _write_line(output, f"JSON report: {json_path}")
            _write_line(output, f"Markdown report: {markdown_path}")

        return EXIT_OK
    except FileExistsError as error:
        _write_line(error_output, f"Error: report already exists: {error.filename}")
    except (KosmosError, OSError, ValueError) as error:
        _write_line(error_output, f"Error: {error}")

    return EXIT_ERROR


def render_scenario_list() -> str:
    """Render the versioned catalog without requiring Ollama."""

    quick = {scenario.identifier for scenario in select_suite("quick")}
    full = {scenario.identifier for scenario in select_suite("full")}
    performance = {scenario.identifier for scenario in select_suite("performance")}
    lines = [f"Kosmos benchmark scenarios (version {SCENARIO_VERSION})"]
    for scenario in list_scenarios():
        suites = []
        if scenario.identifier in quick:
            suites.append("quick")
        if scenario.identifier in full:
            suites.append("full")
        if scenario.identifier in performance:
            suites.append("performance")
        lines.append(
            f"  {scenario.identifier:<28} {scenario.category.value:<14} [{', '.join(suites)}]"
        )
    return "\n".join(lines)


def _metadata(
    config: BenchmarkConfig,
    settings: ApplicationSettings,
    digest: str,
    ollama_version: str,
    execution_mode: ExecutionMode,
) -> BenchmarkMetadata:
    policies = {
        level.value: {
            "thinking": policy.thinking,
            "tools_enabled": policy.tools_enabled,
            "max_inferences": policy.max_inferences,
            "max_tool_calls": policy.max_tool_calls,
            "deadline_seconds": policy.deadline_seconds,
        }
        for level, policy in default_effort_policies().items()
    }
    return BenchmarkMetadata(
        kosmos_version=version("kosmos"),
        model=config.model,
        model_digest=digest,
        ollama_version=ollama_version,
        execution_mode=execution_mode,
        python_version=platform.python_version(),
        operating_system=platform.system(),
        context_length=settings.ollama_context_length,
        effort_policies=policies,
        repetitions=config.repetitions,
        warmup_runs=config.warmup_runs,
        scenario_version=SCENARIO_VERSION,
        started_at=datetime.now(UTC),
    )


def _find_model(name: str, models: Sequence[OllamaModel]) -> OllamaModel | None:
    return next((model for model in models if name in {model.name, model.model}), None)


def _positive_integer(value: str) -> int:
    parsed = _non_negative_integer(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _non_negative_integer(value: str) -> int:
    if not value.isdecimal():
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return int(value)


def _write_line(output: Output, content: str) -> None:
    output.write(content + "\n")
    output.flush()


if __name__ == "__main__":
    raise SystemExit(main())
