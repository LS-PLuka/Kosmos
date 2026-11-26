"""Plain terminal presentation with untrusted-control-sequence neutralization."""

import re
from collections.abc import Iterable

from kosmos.core.orchestration import OrchestrationMetrics, OrchestrationResult
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolDefinition

_CONTROL_SEQUENCE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[PX^_].*?\x1b\\)",
    re.DOTALL,
)


class StreamSanitizer:
    """Sanitize untrusted streamed text while retaining split escape sequences."""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, content: str) -> str:
        """Return safe complete text and buffer a possible partial escape sequence."""

        combined = self._pending + content
        self._pending = ""
        escape_index = combined.rfind("\x1b")

        if escape_index >= 0 and not _escape_is_complete(combined[escape_index:]):
            self._pending = combined[escape_index:]
            combined = combined[:escape_index]

        return sanitize_terminal_text(combined)

    def finish(self) -> str:
        """Discard an incomplete unsafe sequence and return no synthetic content."""

        self._pending = ""
        return ""


def sanitize_terminal_text(content: str) -> str:
    """Remove terminal control sequences while preserving readable Unicode layout."""

    without_sequences = _CONTROL_SEQUENCE.sub("", content)
    return "".join(
        character
        for character in without_sequences
        if character in "\n\r\t" or (ord(character) >= 32 and ord(character) != 127)
    )


def render_banner(
    *,
    version: str,
    ollama_version: str,
    model: str,
    effort: str,
    thinking: bool,
    tool_names: Iterable[str],
) -> str:
    """Render verified runtime information without claiming broader availability."""

    safe_version = sanitize_terminal_text(version)
    safe_ollama_version = sanitize_terminal_text(ollama_version)
    safe_model = sanitize_terminal_text(model)
    tools = ", ".join(sanitize_terminal_text(name) for name in tool_names) or "Disabled"
    return (
        "K O S M O S\n\n"
        "The intelligence orbiting your world.\n\n"
        f"Version:        {safe_version}\n"
        "Provider:       Ollama\n"
        f"Ollama version: {safe_ollama_version}\n"
        f"Model:          {safe_model}\n"
        "Connection:     Local loopback (verified)\n"
        f"Effort:         {effort.upper()}\n"
        f"Thinking:       {_enabled(thinking)}\n"
        f"Tools:          {tools}\n\n"
        "Kosmos: At your service.\n"
    )


def render_tools(definitions: Iterable[ToolDefinition], authorized: frozenset[str]) -> str:
    """Render tool descriptions and effective authorization."""

    lines = ["Tools"]
    for definition in definitions:
        status = "authorized" if definition.name in authorized else "disabled"
        lines.append(f"  {definition.name}: {definition.description} ({status})")

    return "\n".join(lines)


def render_metrics(metrics: OrchestrationMetrics) -> str:
    """Render measured complete-turn metrics and optional provider values."""

    lines = [
        "Metrics",
        f"  Effort: {metrics.effort.value.upper()}",
        f"  Thinking: {_enabled(metrics.thinking)}",
        f"  Elapsed (software): {metrics.elapsed_seconds:.2f}s",
        f"  Inferences: {metrics.inferences_completed}/{metrics.inferences_started}",
        f"  Tool proposals: {metrics.tool_proposals}",
        f"  Tools executed: {metrics.handlers_invoked}",
        f"  Successful tools: {metrics.tools_succeeded}",
        f"  Failed or rejected tools: {metrics.tools_rejected_or_failed}",
    ]
    for inference in metrics.inference_metrics:
        lines.extend(_provider_metric_lines(inference))

    return "\n".join(lines)


def render_stream_metrics(
    *,
    effort: str,
    thinking: bool,
    elapsed_seconds: float,
    inference: InferenceMetrics | None,
) -> str:
    """Render the smaller set of metrics available from a streaming turn."""

    lines = [
        "Metrics",
        f"  Effort: {effort.upper()}",
        f"  Thinking: {_enabled(thinking)}",
        f"  Elapsed (software): {elapsed_seconds:.2f}s",
        "  Inferences: 1",
    ]
    if inference is not None:
        lines.extend(_provider_metric_lines(inference))

    return "\n".join(lines)


def render_result_error(result: OrchestrationResult) -> str:
    """Translate a controlled orchestration status into actionable presentation text."""

    messages = {
        "context_limit": "The request exceeds the configured context budget. "
        "Try a shorter message or clear the conversation.",
        "inference_limit": "The inference limit was reached before a final response.",
        "tool_limit": "The tool-call limit was reached before a final response.",
        "timeout": "The orchestration deadline was exceeded.",
        "provider_unavailable": "The local Ollama service became unavailable.",
        "invalid_response": "Ollama returned an invalid response.",
    }
    return f"Error: {messages.get(result.status.value, 'The request could not be completed.')}"


def _provider_metric_lines(metrics: InferenceMetrics) -> list[str]:
    lines: list[str] = []
    fields = (
        ("Prompt tokens", metrics.prompt_eval_count),
        ("Generated tokens", metrics.eval_count),
        ("Provider duration", _seconds(metrics.total_duration_ns)),
        ("Load duration", _seconds(metrics.load_duration_ns)),
        ("Prompt evaluation", _seconds(metrics.prompt_eval_duration_ns)),
        ("Generation", _seconds(metrics.eval_duration_ns)),
    )
    for label, value in fields:
        if value is not None:
            suffix = "s" if isinstance(value, float) else ""
            rendered = f"{value:.3f}" if isinstance(value, float) else str(value)
            lines.append(f"  {label}: {rendered}{suffix}")

    if metrics.eval_count is not None and metrics.eval_duration_ns:
        tokens_per_second = metrics.eval_count / (metrics.eval_duration_ns / 1_000_000_000)
        lines.append(f"  Tokens per second: {tokens_per_second:.2f}")

    return lines


def _seconds(nanoseconds: int | None) -> float | None:
    return None if nanoseconds is None else nanoseconds / 1_000_000_000


def _enabled(value: bool) -> str:
    return "Enabled" if value else "Disabled"


def _escape_is_complete(value: str) -> bool:
    if value.startswith("\x1b]"):
        return "\x07" in value or "\x1b\\" in value
    if value.startswith(("\x1bP", "\x1bX", "\x1b^", "\x1b_")):
        return "\x1b\\" in value
    if value.startswith("\x1b["):
        return bool(re.search(r"[@-~]$", value[2:]))
    return len(value) >= 2
