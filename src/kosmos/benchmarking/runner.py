"""Benchmark execution through the public Core Orchestrator API."""

import asyncio
import time
from dataclasses import replace
from uuid import UUID

from kosmos.benchmarking.evaluation import evaluate
from kosmos.benchmarking.models import (
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkStatus,
    PerformanceEvidence,
    ScenarioResult,
)
from kosmos.core.orchestration import CoreOrchestrator, OrchestrationStatus
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolAuthorization, ToolResult


async def run_benchmark(
    orchestrator: CoreOrchestrator,
    scenarios: tuple[BenchmarkScenario, ...],
    config: BenchmarkConfig,
    metadata: BenchmarkMetadata,
) -> BenchmarkRun:
    """Run warm-ups and measured repetitions using independent sessions."""

    results: list[ScenarioResult] = []
    for scenario in scenarios:
        for warmup_index in range(config.warmup_runs):
            result = await _run_scenario(
                orchestrator,
                scenario,
                config.model,
                warmup_index + 1,
                warmup=True,
            )
            results.append(
                replace(
                    result,
                    status=BenchmarkStatus.SKIPPED,
                    reason="warm-up run excluded from primary statistics",
                )
            )

        for repetition in range(1, config.repetitions + 1):
            results.append(
                await _run_scenario(
                    orchestrator,
                    scenario,
                    config.model,
                    repetition,
                    warmup=False,
                )
            )

    return BenchmarkRun(config, metadata, tuple(results))


async def _run_scenario(
    orchestrator: CoreOrchestrator,
    scenario: BenchmarkScenario,
    model: str,
    repetition: int,
    *,
    warmup: bool,
) -> ScenarioResult:
    session = orchestrator.create_session()

    try:
        if scenario.streaming:
            return await _run_streaming(
                orchestrator,
                session.session_id,
                scenario,
                model,
                repetition,
                warmup,
            )

        return await _run_complete(
            orchestrator,
            session.session_id,
            scenario,
            model,
            repetition,
            warmup,
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        return ScenarioResult(
            scenario.identifier,
            scenario.category,
            repetition,
            warmup,
            BenchmarkStatus.ERROR,
            None,
            f"{type(error).__name__}: {error}",
        )
    finally:
        if not orchestrator.get_session(session.session_id).is_busy:
            orchestrator.delete_session(session.session_id)


async def _run_complete(
    orchestrator: CoreOrchestrator,
    session_id: UUID,
    scenario: BenchmarkScenario,
    model: str,
    repetition: int,
    warmup: bool,
) -> ScenarioResult:
    authorization = ToolAuthorization(scenario.authorized_tools)
    tool_results: list[ToolResult] = []
    metrics: list[InferenceMetrics] = []
    final_result = None
    started_at = time.monotonic()

    for message in scenario.messages:
        final_result = await orchestrator.generate(
            session_id,
            message,
            model=model,
            effort=scenario.effort,
            authorization=authorization,
            selected_tools=scenario.selected_tools,
        )
        tool_results.extend(final_result.tool_results)
        metrics.extend(final_result.metrics.inference_metrics)

        if final_result.status is not OrchestrationStatus.COMPLETED:
            break

    if final_result is None:
        raise AssertionError("validated scenario has no messages")

    assessment = evaluate(
        scenario,
        orchestration_status=final_result.status,
        response=final_result.content,
        tool_results=tuple(tool_results),
    )
    performance = PerformanceEvidence(
        time.monotonic() - started_at,
        inference_metrics=tuple(metrics),
    )
    return ScenarioResult(
        scenario.identifier,
        scenario.category,
        repetition,
        warmup,
        assessment.status,
        final_result.content,
        assessment.reason,
        assessment.checks,
        final_result.metrics,
        performance,
        tuple(tool_results),
    )


async def _run_streaming(
    orchestrator: CoreOrchestrator,
    session_id: UUID,
    scenario: BenchmarkScenario,
    model: str,
    repetition: int,
    warmup: bool,
) -> ScenarioResult:
    started_at = time.monotonic()
    first_text_seconds = None
    parts: list[str] = []
    provider_metrics: list[InferenceMetrics] = []
    stream = orchestrator.stream(
        session_id,
        scenario.messages[-1],
        model=model,
        effort=scenario.effort,
    )

    try:
        async for chunk in stream:
            parts.append(chunk.content)
            if first_text_seconds is None and chunk.content:
                first_text_seconds = time.monotonic() - started_at
            if chunk.metrics is not None:
                provider_metrics.append(chunk.metrics)
    finally:
        await stream.aclose()

    response = "".join(parts)
    assessment = evaluate(
        scenario,
        orchestration_status=OrchestrationStatus.COMPLETED,
        response=response,
        tool_results=(),
    )
    performance = PerformanceEvidence(
        time.monotonic() - started_at,
        first_text_seconds,
        tuple(provider_metrics),
    )
    return ScenarioResult(
        scenario.identifier,
        scenario.category,
        repetition,
        warmup,
        assessment.status,
        response,
        assessment.reason,
        assessment.checks,
        performance=performance,
    )
