"""Safe terminal, JSON, and Markdown benchmark reporting."""

import json
import statistics
from collections import Counter
from pathlib import Path

from kosmos.benchmarking.models import BenchmarkRun, BenchmarkStatus, ScenarioResult
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolResult


def render_terminal(run: BenchmarkRun) -> str:
    """Render measured live results without turning manual review into a pass."""

    lines = [
        "KOSMOS MODEL BENCHMARK",
        "",
        f"Model: {run.config.model}",
        f"Suite: {run.config.suite}",
        f"Execution: {run.metadata.execution_mode.value}",
        "",
    ]
    measured = tuple(result for result in run.results if not result.warmup)
    categories = dict.fromkeys(result.category for result in measured)
    for category in categories:
        lines.append(category.value.replace("_", " ").title())
        for result in measured:
            if result.category is category:
                lines.append(
                    f"  {result.scenario_id} (run {result.repetition}) ..... {result.status.value}"
                )
        lines.append("")

    elapsed = [
        result.performance.elapsed_seconds for result in measured if result.performance is not None
    ]
    rates = [_tokens_per_second(result) for result in measured]
    available_rates = [rate for rate in rates if rate is not None]
    if elapsed:
        lines.extend(
            [
                "Performance",
                f"  Median latency: {statistics.median(elapsed):.3f}s",
                "  Generation speed: "
                + (
                    f"{statistics.median(available_rates):.2f} tokens/s (median)"
                    if available_rates
                    else "unavailable"
                ),
                "",
            ]
        )

    counts = Counter(result.status for result in measured)
    lines.extend(
        [
            "Summary",
            f"  Passed: {counts[BenchmarkStatus.PASS]}",
            f"  Failed: {counts[BenchmarkStatus.FAIL]}",
            f"  Errors: {counts[BenchmarkStatus.ERROR]}",
            f"  Skipped: {counts[BenchmarkStatus.SKIPPED]}",
            f"  Manual review: {counts[BenchmarkStatus.MANUAL_REVIEW]}",
            "",
            "Validation: PENDING MAINTAINER REVIEW",
        ]
    )
    return "\n".join(lines)


def render_markdown(run: BenchmarkRun) -> str:
    """Render a reviewable report with explicit warm-up identification."""

    lines = [
        "# Kosmos Model Benchmark",
        "",
        f"- Model: `{run.config.model}`",
        f"- Suite: `{run.config.suite}`",
        f"- Execution: `{run.metadata.execution_mode.value}`",
        f"- Started: `{run.metadata.started_at.isoformat()}`",
        f"- Scenario version: `{run.metadata.scenario_version}`",
        "",
        "## Results",
        "",
        "| Scenario | Run | Warm-up | Status | Reason |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for result in run.results:
        reason = result.reason.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{result.scenario_id}` | {result.repetition} | "
            f"{'yes' if result.warmup else 'no'} | {result.status.value} | {reason} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Warm-up runs are shown but excluded from primary statistics. Text heuristics are not "
            "semantic proof. MANUAL_REVIEW results are not counted as deterministic passes.",
            "",
            "**Validation: PENDING MAINTAINER REVIEW**",
            "",
        ]
    )
    return "\n".join(lines)


def export_reports(run: BenchmarkRun, output_base: Path) -> tuple[Path, Path]:
    """Create JSON and Markdown reports without silently overwriting files."""

    if not isinstance(output_base, Path):
        raise TypeError("output_base must be a Path")

    json_path = output_base.with_suffix(".json")
    markdown_path = output_base.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)

    document = _run_document(run)
    with json_path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(document, file, ensure_ascii=False, indent=2)
        file.write("\n")
    try:
        with markdown_path.open("x", encoding="utf-8", newline="\n") as file:
            file.write(render_markdown(run))
    except Exception:
        json_path.unlink()
        raise

    return json_path, markdown_path


def _run_document(run: BenchmarkRun) -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution": run.metadata.execution_mode.value,
        "validation": "pending_maintainer_review",
        "config": {
            "suite": run.config.suite,
            "model": run.config.model,
            "repetitions": run.config.repetitions,
            "warmup_runs": run.config.warmup_runs,
        },
        "metadata": {
            "kosmos_version": run.metadata.kosmos_version,
            "model": run.metadata.model,
            "model_digest": run.metadata.model_digest,
            "ollama_version": run.metadata.ollama_version,
            "execution_mode": run.metadata.execution_mode.value,
            "python_version": run.metadata.python_version,
            "operating_system": run.metadata.operating_system,
            "context_length": run.metadata.context_length,
            "effort_policies": {
                name: dict(values) for name, values in run.metadata.effort_policies.items()
            },
            "repetitions": run.metadata.repetitions,
            "warmup_runs": run.metadata.warmup_runs,
            "scenario_version": run.metadata.scenario_version,
            "started_at": run.metadata.started_at.isoformat(),
        },
        "results": [_result_document(result) for result in run.results],
    }


def _result_document(result: ScenarioResult) -> dict[str, object]:
    return {
        "scenario_id": result.scenario_id,
        "category": result.category.value,
        "repetition": result.repetition,
        "warmup": result.warmup,
        "status": result.status.value,
        "response": result.response,
        "reason": result.reason,
        "checks": list(result.checks),
        "orchestration_metrics": _orchestration_document(result),
        "performance": _performance_document(result),
        "tool_results": [_tool_result_document(item) for item in result.tool_results],
    }


def _orchestration_document(result: ScenarioResult) -> dict[str, object] | None:
    metrics = result.orchestration_metrics
    if metrics is None:
        return None
    return {
        "elapsed_seconds": metrics.elapsed_seconds,
        "inferences_started": metrics.inferences_started,
        "inferences_completed": metrics.inferences_completed,
        "tool_proposals": metrics.tool_proposals,
        "handlers_invoked": metrics.handlers_invoked,
        "tools_succeeded": metrics.tools_succeeded,
        "tools_rejected_or_failed": metrics.tools_rejected_or_failed,
        "effort": metrics.effort.value,
        "thinking": metrics.thinking,
        "inference_metrics": [_inference_document(item) for item in metrics.inference_metrics],
    }


def _performance_document(result: ScenarioResult) -> dict[str, object] | None:
    performance = result.performance
    if performance is None:
        return None
    return {
        "elapsed_seconds": performance.elapsed_seconds,
        "first_text_seconds": performance.first_text_seconds,
        "inference_metrics": [_inference_document(item) for item in performance.inference_metrics],
    }


def _inference_document(metrics: InferenceMetrics) -> dict[str, int | None]:
    return {
        "total_duration_ns": metrics.total_duration_ns,
        "load_duration_ns": metrics.load_duration_ns,
        "prompt_eval_count": metrics.prompt_eval_count,
        "prompt_eval_duration_ns": metrics.prompt_eval_duration_ns,
        "eval_count": metrics.eval_count,
        "eval_duration_ns": metrics.eval_duration_ns,
    }


def _tool_result_document(result: ToolResult) -> dict[str, object]:
    return {
        "call_id": result.call_id,
        "tool_name": result.tool_name,
        "status": result.status.value,
        "data": result.to_payload()["data"],
        "error_code": result.error_code,
        "message": result.message,
    }


def _tokens_per_second(result: ScenarioResult) -> float | None:
    if result.performance is None:
        return None

    generated = 0
    duration = 0
    found = False
    for metrics in result.performance.inference_metrics:
        if metrics.eval_count is not None and metrics.eval_duration_ns is not None:
            generated += metrics.eval_count
            duration += metrics.eval_duration_ns
            found = True

    if not found or duration <= 0:
        return None
    return generated / (duration / 1_000_000_000)
