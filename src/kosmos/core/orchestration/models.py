"""Public immutable results and operational metrics for core orchestration."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from kosmos.core.orchestration.effort import EffortLevel
from kosmos.intelligence.conversation import ContextSelectionMetrics
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools.models import ToolCall, ToolResult


class OrchestrationStatus(str, Enum):
    """Stable terminal states that are safe for application-level handling."""

    COMPLETED = "completed"
    INFERENCE_LIMIT = "inference_limit"
    TOOL_LIMIT = "tool_limit"
    CONTEXT_LIMIT = "context_limit"
    TIMEOUT = "timeout"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_HTTP_ERROR = "provider_http_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"
    INFERENCE_ERROR = "inference_error"


@dataclass(frozen=True, slots=True)
class ContextRequestMetrics:
    """Integrated serialized-budget measurements for one provider request."""

    request_kind: str
    character_budget: int
    serialized_request_characters: int
    selected_message_characters: int
    response_reserve_characters: int
    omitted_history_turns: int
    context_limit_reached: bool


@dataclass(frozen=True, slots=True)
class ContextMetrics:
    """Measurements from conversation selection and subsequent provider requests."""

    conversation: ContextSelectionMetrics | None = None
    requests: tuple[ContextRequestMetrics, ...] = ()


@dataclass(frozen=True, slots=True)
class OrchestrationMetrics:
    """Measured coordination counts without inventing unavailable provider values."""

    elapsed_seconds: float
    inferences_started: int
    inferences_completed: int
    tool_proposals: int
    handlers_invoked: int
    tools_succeeded: int
    tools_rejected_or_failed: int
    effort: EffortLevel
    thinking: bool
    inference_metrics: tuple[InferenceMetrics, ...] = ()
    context: ContextMetrics = ContextMetrics()
    inference_metric_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """One completed or controlled terminal orchestration outcome."""

    session_id: UUID
    model: str
    effort: EffortLevel
    status: OrchestrationStatus
    content: str | None
    tool_results: tuple[ToolResult, ...]
    metrics: OrchestrationMetrics
    failure: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
