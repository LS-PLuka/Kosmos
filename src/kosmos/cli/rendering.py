"""Plain terminal presentation with untrusted-control-sequence neutralization."""

import re
from collections.abc import Iterable

from kosmos.core.orchestration import ContextMetrics, OrchestrationMetrics, OrchestrationResult
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolDefinition, ToolResult, ToolResultStatus

_CONTROL_SEQUENCE = re.compile(
    r"(?:"
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[PX^_].*?\x1b\\)"
    r"|\x9b[0-?]*[ -/]*[@-~]"
    r"|\x9d[^\x07\x9c]*(?:\x07|\x9c)"
    r"|[\x90\x98\x9e\x9f].*?\x9c"
    r")",
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
        escape_index = _last_sequence_start(combined)

        if escape_index >= 0 and not _control_sequence_is_complete(combined[escape_index:]):
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
        if character in "\n\t" or 32 <= ord(character) <= 126 or ord(character) >= 160
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
        "Connection:     Local loopback (verified at startup)\n"
        f"Effort:         {effort.upper()}\n"
        f"Thinking:       {_enabled(thinking)}\n"
        f"Tools:          {tools}\n\n"
        "Kosmos: À sua disposição, senhor.\n"
    )


def render_tools(definitions: Iterable[ToolDefinition], authorized: frozenset[str]) -> str:
    """Render tool descriptions and effective authorization."""

    lines = ["Tools"]
    for definition in definitions:
        status = "available" if definition.name in authorized else "registered, disabled"
        lines.append(f"  {definition.name}: {definition.description} ({status})")

    return "\n".join(lines)


def render_tool_results(results: Iterable[ToolResult]) -> str:
    """Render only trusted execution evidence and compact pure-tool values."""

    lines: list[str] = []
    for result in results:
        label = sanitize_terminal_text(result.tool_name)
        lines.append(f"[{label}: {result.status.value}]")

        value = _compact_tool_value(result)
        if value is not None:
            lines.append(f"Result: {sanitize_terminal_text(value)}")

    return "\n".join(lines)


def render_execution_evidence(result: OrchestrationResult) -> str:
    """Render proposals and outcomes without exposing untrusted tool arguments."""

    results_by_call = {item.call_id: item for item in result.tool_results}
    rendered_call_ids: set[str] = set()
    blocks: list[str] = []

    for call in result.tool_calls:
        rendered_call_ids.add(call.call_id)
        outcome = results_by_call.get(call.call_id)
        if outcome is None:
            blocks.append(f"[{sanitize_terminal_text(call.name)}: proposed]")
        else:
            blocks.append(render_tool_results((outcome,)))

    uncorrelated = (item for item in result.tool_results if item.call_id not in rendered_call_ids)
    trailing = render_tool_results(uncorrelated)
    if trailing:
        blocks.append(trailing)

    return "\n".join(blocks)


def render_metrics(
    metrics: OrchestrationMetrics,
    *,
    provider_context_tokens: int | None = None,
) -> str:
    """Render measured complete-turn metrics and optional provider values."""

    lines = [
        "Metrics",
        f"  Effort: {metrics.effort.value.upper()}",
        f"  Thinking: {_enabled(metrics.thinking)}",
        f"  Elapsed (software): {metrics.elapsed_seconds:.2f}s",
        f"  Inferences: {metrics.inferences_completed}/{metrics.inferences_started}",
        f"  Tool proposals: {metrics.tool_proposals}",
        f"  Handlers invoked: {metrics.handlers_invoked}",
        f"  Successful tools: {metrics.tools_succeeded}",
        f"  Failed or rejected tools: {metrics.tools_rejected_or_failed}",
    ]
    indexed_metrics = _indexed_inference_metrics(metrics)
    if metrics.inferences_started > 1:
        for index in range(1, metrics.inferences_started + 1):
            lines.append(f"  Inference {index}")
            inference = indexed_metrics.get(index)
            if inference is None:
                lines.append("    Provider metrics: unavailable")
            else:
                lines.extend(_provider_metric_lines(inference, indent="    "))
    elif indexed_metrics:
        lines.extend(_provider_metric_lines(next(iter(indexed_metrics.values()))))

    lines.extend(_context_metric_lines(metrics.context, provider_context_tokens))

    return "\n".join(lines)


def render_stream_metrics(
    *,
    effort: str,
    thinking: bool,
    elapsed_seconds: float,
    inference: InferenceMetrics | None,
    context: ContextMetrics | None = None,
    time_to_first_visible_text: float | None = None,
    provider_context_tokens: int | None = None,
) -> str:
    """Render the smaller set of metrics available from a streaming turn."""

    lines = [
        "Metrics",
        f"  Effort: {effort.upper()}",
        f"  Thinking: {_enabled(thinking)}",
        f"  Elapsed (software): {elapsed_seconds:.2f}s",
        "  Inferences: 1/1",
    ]
    if inference is not None:
        lines.extend(_provider_metric_lines(inference))
    if time_to_first_visible_text is not None:
        lines.append(f"  Time to first visible text: {time_to_first_visible_text:.3f}s")

    lines.extend(_context_metric_lines(context or ContextMetrics(), provider_context_tokens))

    return "\n".join(lines)


def render_result_error(result: OrchestrationResult) -> str:
    """Translate a controlled orchestration status into actionable presentation text."""

    messages = {
        "context_limit": "The request exceeds the configured context budget. "
        "Try a shorter message or clear the conversation.",
        "inference_limit": "The inference limit was reached before a final response.",
        "tool_limit": "The tool-call limit was reached before a final response.",
        "timeout": "The orchestration deadline was exceeded.",
        "provider_timeout": "The local Ollama request timed out.",
        "provider_http_error": "Ollama returned an unsuccessful HTTP response.",
        "provider_unavailable": "The local Ollama service became unavailable.",
        "invalid_response": "Ollama returned an invalid response.",
        "inference_error": "Ollama could not complete the inference.",
    }
    return f"Error: {messages.get(result.status.value, 'The request could not be completed.')}"


def _provider_metric_lines(metrics: InferenceMetrics, *, indent: str = "  ") -> list[str]:
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
            lines.append(f"{indent}{label}: {rendered}{suffix}")

    if metrics.eval_count is not None and metrics.eval_duration_ns:
        tokens_per_second = metrics.eval_count / (metrics.eval_duration_ns / 1_000_000_000)
        lines.append(f"{indent}Tokens per second: {tokens_per_second:.2f}")

    return lines


def _indexed_inference_metrics(
    metrics: OrchestrationMetrics,
) -> dict[int, InferenceMetrics]:
    indices = metrics.inference_metric_indices
    if not indices:
        indices = tuple(range(1, len(metrics.inference_metrics) + 1))

    return dict(zip(indices, metrics.inference_metrics, strict=True))


def _seconds(nanoseconds: int | None) -> float | None:
    return None if nanoseconds is None else nanoseconds / 1_000_000_000


def _compact_tool_value(result: ToolResult) -> str | None:
    if result.status is not ToolResultStatus.SUCCESS or result.tool_name not in {
        "calculate",
        "count_items",
    }:
        return None

    data = result.data
    if not hasattr(data, "get"):
        return None

    value = data.get("result") if result.tool_name == "calculate" else data.get("count")
    return str(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _enabled(value: bool) -> str:
    return "Enabled" if value else "Disabled"


def _context_metric_lines(
    metrics: ContextMetrics,
    provider_context_tokens: int | None,
) -> list[str]:
    if metrics.conversation is None and not metrics.requests:
        return []

    lines = ["Context"]
    if provider_context_tokens is not None:
        lines.append(f"  Provider context: {provider_context_tokens} configured tokens")
    conversation = metrics.conversation
    if conversation is not None:
        lines.extend(
            (
                "  History selected: "
                f"{conversation.selected_history_turns}/{conversation.total_confirmed_turns} "
                "turns",
                f"  History eligible: {conversation.eligible_history_turns} turns",
                f"  History omitted: {conversation.omitted_history_turns} turns",
                f"    By turn limit: {conversation.omitted_by_turn_limit} turns",
                f"    By conversation budget: {conversation.omitted_by_character_limit} turns",
                f"  Conversation budget: {conversation.character_budget} characters",
                f"  Conversation selection: {conversation.selected_message_characters} characters",
            )
        )

    request_count = len(metrics.requests)
    for index, request in enumerate(metrics.requests, start=1):
        label = "Final provider request" if request_count == 1 else f"Provider request {index}"
        lines.extend(
            (
                f"  {label} ({request.request_kind})",
                "    Serialized input: "
                f"{request.serialized_request_characters}/{request.character_budget} characters",
                f"    Selected messages: {request.selected_message_characters} characters",
                f"    Response reserve: {request.response_reserve_characters} characters",
                "    Additional history omitted by integrated budget: "
                f"{request.omitted_history_turns} turns",
            )
        )

    return lines


def _last_sequence_start(value: str) -> int:
    return max(value.rfind(character) for character in "\x1b\x90\x98\x9b\x9d\x9e\x9f")


def _control_sequence_is_complete(value: str) -> bool:
    if value.startswith(("\x1b]", "\x9d")):
        if value.startswith("\x1b]"):
            return "\x07" in value or "\x1b\\" in value
        return "\x07" in value or "\x9c" in value
    if value.startswith(("\x1bP", "\x1bX", "\x1b^", "\x1b_")):
        return "\x1b\\" in value
    if value.startswith(("\x90", "\x98", "\x9e", "\x9f")):
        return "\x9c" in value
    if value.startswith("\x1b["):
        return bool(re.search(r"[@-~]$", value[2:]))
    if value.startswith("\x9b"):
        return bool(re.search(r"[@-~]$", value[1:]))
    return len(value) >= 2
