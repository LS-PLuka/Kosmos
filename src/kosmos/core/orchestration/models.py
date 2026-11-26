"""Public immutable results and operational metrics for core orchestration."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from kosmos.core.orchestration.effort import EffortLevel
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools.models import ToolResult


class OrchestrationStatus(str, Enum):
    """Stable terminal states that are safe for application-level handling."""

    COMPLETED = "completed"
    INFERENCE_LIMIT = "inference_limit"
    TOOL_LIMIT = "tool_limit"
    CONTEXT_LIMIT = "context_limit"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"


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
