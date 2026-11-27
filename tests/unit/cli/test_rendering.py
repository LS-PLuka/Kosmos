"""Tests for safe plain-text terminal rendering."""

from uuid import uuid4

from kosmos.cli.rendering import (
    StreamSanitizer,
    render_banner,
    render_execution_evidence,
    render_metrics,
    render_stream_metrics,
    render_tool_results,
    sanitize_terminal_text,
)
from kosmos.core.orchestration import (
    ContextMetrics,
    ContextRequestMetrics,
    EffortLevel,
    OrchestrationMetrics,
    OrchestrationResult,
    OrchestrationStatus,
)
from kosmos.intelligence.conversation import ContextSelectionMetrics
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolCall, ToolResult, ToolResultStatus


def test_sanitization_preserves_unicode_whitespace_and_tabs() -> None:
    content = "Olá, senhor.\n\tPróxima linha."

    assert sanitize_terminal_text(content) == content


def test_sanitization_removes_ansi_osc_and_control_characters() -> None:
    content = "safe\x1b[31mred\x1b[0m\x1b]0;title\x07\x00text\rhidden\x7f"

    assert sanitize_terminal_text(content) == "saferedtexthidden"


def test_sanitization_removes_c1_sequences_without_leaking_parameters() -> None:
    content = "safe\x9b31mred\x9b0m\x9d0;title\x9ctext\x85"

    assert sanitize_terminal_text(content) == "saferedtext"


def test_banner_sanitizes_runtime_metadata() -> None:
    rendered = render_banner(
        version="0.1.0",
        ollama_version="1.0\x1b[31m",
        model="safe\x1b]0;title\x07-model",
        effort="low",
        thinking=False,
        tool_names=("calculate",),
    )

    assert "\x1b" not in rendered
    assert "safe-model" in rendered
    assert "Kosmos: À sua disposição, senhor." in rendered
    assert "Offline" not in rendered


def test_stream_sanitizer_handles_split_ansi_sequence() -> None:
    sanitizer = StreamSanitizer()

    assert sanitizer.feed("Hello\x1b[") == "Hello"
    assert sanitizer.feed("31mworld\x1b[0m") == "world"
    assert sanitizer.finish() == ""


def test_stream_sanitizer_handles_split_osc_sequence() -> None:
    sanitizer = StreamSanitizer()

    assert sanitizer.feed("before\x1b]0;bad") == "before"
    assert sanitizer.feed(" title\x07after") == "after"


def test_stream_sanitizer_handles_split_c1_sequence() -> None:
    sanitizer = StreamSanitizer()

    assert sanitizer.feed("before\x9b") == "before"
    assert sanitizer.feed("31mafter") == "after"


def test_complete_metrics_keep_units_distinct() -> None:
    provider_metrics = InferenceMetrics(
        total_duration_ns=2_000_000_000,
        load_duration_ns=500_000_000,
        prompt_eval_count=10,
        eval_count=20,
        eval_duration_ns=1_000_000_000,
    )
    metrics = OrchestrationMetrics(
        elapsed_seconds=2.5,
        inferences_started=1,
        inferences_completed=1,
        tool_proposals=0,
        handlers_invoked=0,
        tools_succeeded=0,
        tools_rejected_or_failed=0,
        effort=EffortLevel.LOW,
        thinking=False,
        inference_metrics=(provider_metrics,),
    )

    rendered = render_metrics(metrics)

    assert "Elapsed (software): 2.50s" in rendered
    assert "Provider duration: 2.000s" in rendered
    assert "Load duration: 0.500s" in rendered
    assert "Tokens per second: 20.00" in rendered


def test_missing_provider_metrics_are_not_invented() -> None:
    rendered = render_stream_metrics(
        effort="instant",
        thinking=False,
        elapsed_seconds=0.25,
        inference=None,
    )

    assert "Elapsed (software): 0.25s" in rendered
    assert "Prompt tokens" not in rendered
    assert "Provider duration" not in rendered
    assert "Tokens per second" not in rendered


def test_tokens_per_second_requires_positive_generation_duration() -> None:
    rendered = render_stream_metrics(
        effort="instant",
        thinking=False,
        elapsed_seconds=0.1,
        inference=InferenceMetrics(eval_count=10, eval_duration_ns=0),
    )

    assert "Tokens per second" not in rendered


def test_tool_results_render_trusted_status_and_compact_pure_value() -> None:
    result = ToolResult(
        "call-1",
        "calculate",
        ToolResultStatus.SUCCESS,
        {"result": 4_000},
    )

    assert render_tool_results((result,)) == "[calculate: success]\nResult: 4000"


def test_tool_results_distinguish_rejected_and_failed_execution() -> None:
    rejected = ToolResult(
        "call-1",
        "calculate",
        ToolResultStatus.UNAUTHORIZED,
        error_code="unauthorized",
        message="Denied",
    )
    failed = ToolResult(
        "call-2",
        "calculate",
        ToolResultStatus.EXECUTION_FAILED,
        error_code="execution_failed",
        message="Failed",
    )

    assert render_tool_results((rejected, failed)) == (
        "[calculate: unauthorized]\n[calculate: execution_failed]"
    )


def test_execution_evidence_shows_unexecuted_proposal_without_arguments() -> None:
    call = ToolCall("call_1", "calculate", {"a": 123, "b": 456, "operation": "add"})
    metrics = OrchestrationMetrics(
        elapsed_seconds=0.1,
        inferences_started=1,
        inferences_completed=1,
        tool_proposals=1,
        handlers_invoked=0,
        tools_succeeded=0,
        tools_rejected_or_failed=0,
        effort=EffortLevel.LOW,
        thinking=False,
    )
    result = OrchestrationResult(
        uuid4(),
        "model",
        EffortLevel.LOW,
        OrchestrationStatus.INFERENCE_LIMIT,
        None,
        (),
        metrics,
        tool_calls=(call,),
    )

    rendered = render_execution_evidence(result)

    assert rendered == "[calculate: proposed]"
    assert "123" not in rendered
    assert "456" not in rendered


def test_metrics_identify_inferences_and_context_omission_causes() -> None:
    conversation = ContextSelectionMetrics(8, 6, 4, 4, 2, 2, 8_000, 7_000, True)
    requests = (
        ContextRequestMetrics("tools", 10_000, 7_450, 7_000, 2_000, 1, True),
        ContextRequestMetrics("tools", 10_000, 7_700, 7_100, 2_000, 0, False),
    )
    metrics = OrchestrationMetrics(
        elapsed_seconds=2.5,
        inferences_started=2,
        inferences_completed=2,
        tool_proposals=1,
        handlers_invoked=1,
        tools_succeeded=1,
        tools_rejected_or_failed=0,
        effort=EffortLevel.LOW,
        thinking=False,
        inference_metrics=(InferenceMetrics(eval_count=1), InferenceMetrics(eval_count=2)),
        context=ContextMetrics(conversation, requests),
    )

    rendered = render_metrics(metrics)

    assert "Inference 1" in rendered
    assert "Inference 2" in rendered
    assert "History omitted: 4 turns" in rendered
    assert "By turn limit: 2 turns" in rendered
    assert "By conversation budget: 2 turns" in rendered
    assert "Provider request 1 (tools)" in rendered
    assert "Additional history omitted by integrated budget: 1 turns" in rendered
    assert "characters" in rendered
