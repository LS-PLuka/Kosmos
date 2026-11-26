"""Network-free runner, metrics, and report tests."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from kosmos.benchmarking.models import (
    BenchmarkCategory,
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkScenario,
    BenchmarkStatus,
    EvaluationStrategy,
    ExecutionMode,
)
from kosmos.benchmarking.reporting import export_reports, render_terminal
from kosmos.benchmarking.runner import run_benchmark
from kosmos.core.orchestration import CoreOrchestrator, EffortLevel
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
)


@dataclass(slots=True)
class RepeatingProvider:
    requests: list[InferenceRequest] = field(default_factory=list)

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)
        return InferenceResponse(
            request.model,
            "Completed",
            InferenceMetrics(eval_count=10, eval_duration_ns=1_000_000_000),
        )

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.requests.append(request)
        yield InferenceChunk(
            request.model,
            "Completed",
            True,
            InferenceMetrics(eval_count=10, eval_duration_ns=1_000_000_000),
        )


def _metadata(config: BenchmarkConfig) -> BenchmarkMetadata:
    return BenchmarkMetadata(
        "0.1.0",
        config.model,
        "digest",
        "test",
        ExecutionMode.SIMULATED,
        "3.12",
        "TestOS",
        4096,
        {"low": {"thinking": False}},
        config.repetitions,
        config.warmup_runs,
        "1.0",
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_runner_uses_fresh_sessions_and_excludes_identified_warmups() -> None:
    provider = RepeatingProvider()
    orchestrator = CoreOrchestrator(provider)
    scenario = BenchmarkScenario(
        "completion_case",
        BenchmarkCategory.STABILITY,
        "Completion case",
        ("Prompt",),
        EffortLevel.LOW,
        EvaluationStrategy.COMPLETION,
    )
    config = BenchmarkConfig("quick", "test-model", repetitions=2, warmup_runs=1)

    run = asyncio.run(run_benchmark(orchestrator, (scenario,), config, _metadata(config)))

    assert [result.status for result in run.results] == [
        BenchmarkStatus.SKIPPED,
        BenchmarkStatus.PASS,
        BenchmarkStatus.PASS,
    ]
    assert all(len(request.messages) == 2 for request in provider.requests)


def test_streaming_records_first_text_and_provider_metrics() -> None:
    provider = RepeatingProvider()
    orchestrator = CoreOrchestrator(provider)
    scenario = BenchmarkScenario(
        "stream_case",
        BenchmarkCategory.PERFORMANCE,
        "Streaming case",
        ("Prompt",),
        EffortLevel.INSTANT,
        EvaluationStrategy.COMPLETION,
        streaming=True,
    )
    config = BenchmarkConfig("performance", "test-model")

    run = asyncio.run(run_benchmark(orchestrator, (scenario,), config, _metadata(config)))
    performance = run.results[0].performance

    assert performance is not None
    assert performance.first_text_seconds is not None
    assert performance.inference_metrics[0].eval_count == 10


def test_runner_propagates_cancellation() -> None:
    started = asyncio.Event()

    @dataclass(slots=True)
    class BlockingProvider(RepeatingProvider):
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            self.requests.append(request)
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    provider = BlockingProvider()
    orchestrator = CoreOrchestrator(provider)
    scenario = BenchmarkScenario(
        "cancel_case",
        BenchmarkCategory.STABILITY,
        "Cancellation case",
        ("Prompt",),
        EffortLevel.LOW,
        EvaluationStrategy.COMPLETION,
    )
    config = BenchmarkConfig("quick", "test-model")

    async def cancel_run() -> None:
        task = asyncio.create_task(
            run_benchmark(orchestrator, (scenario,), config, _metadata(config))
        )
        await started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_run())


def test_reports_export_json_and_markdown_without_overwrite(tmp_path) -> None:
    provider = RepeatingProvider()
    orchestrator = CoreOrchestrator(provider)
    scenario = BenchmarkScenario(
        "report_case",
        BenchmarkCategory.PERFORMANCE,
        "Report case",
        ("Prompt",),
        EffortLevel.LOW,
        EvaluationStrategy.COMPLETION,
    )
    config = BenchmarkConfig("performance", "test-model")
    run = asyncio.run(run_benchmark(orchestrator, (scenario,), config, _metadata(config)))

    json_path, markdown_path = export_reports(run, tmp_path / "benchmark-results" / "run")
    document = json.loads(json_path.read_text(encoding="utf-8"))

    assert document["execution"] == "SIMULATED"
    assert document["metadata"]["execution_mode"] == "SIMULATED"
    assert document["validation"] == "pending_maintainer_review"
    assert "PENDING MAINTAINER REVIEW" in markdown_path.read_text(encoding="utf-8")
    terminal = render_terminal(run)
    assert "Execution: SIMULATED" in terminal
    assert "Generation speed: 10.00 tokens/s" in terminal
    with pytest.raises(FileExistsError):
        export_reports(run, tmp_path / "benchmark-results" / "run")
