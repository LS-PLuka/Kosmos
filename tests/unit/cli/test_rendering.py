"""Tests for safe plain-text terminal rendering."""

from kosmos.cli.rendering import (
    StreamSanitizer,
    render_banner,
    render_metrics,
    render_stream_metrics,
    sanitize_terminal_text,
)
from kosmos.core.orchestration import EffortLevel, OrchestrationMetrics
from kosmos.intelligence.models import InferenceMetrics


def test_sanitization_preserves_unicode_whitespace_and_tabs() -> None:
    content = "Olá, senhor.\n\tPróxima linha."

    assert sanitize_terminal_text(content) == content


def test_sanitization_removes_ansi_osc_and_control_characters() -> None:
    content = "safe\x1b[31mred\x1b[0m\x1b]0;title\x07\x00text\x7f"

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


def test_stream_sanitizer_handles_split_ansi_sequence() -> None:
    sanitizer = StreamSanitizer()

    assert sanitizer.feed("Hello\x1b[") == "Hello"
    assert sanitizer.feed("31mworld\x1b[0m") == "world"
    assert sanitizer.finish() == ""


def test_stream_sanitizer_handles_split_osc_sequence() -> None:
    sanitizer = StreamSanitizer()

    assert sanitizer.feed("before\x1b]0;bad") == "before"
    assert sanitizer.feed(" title\x07after") == "after"


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
