"""Immutable benchmark definitions, evidence, and execution records."""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from kosmos.core.orchestration import EffortLevel, OrchestrationMetrics
from kosmos.intelligence.models import InferenceMetrics
from kosmos.intelligence.tools import ToolCall, ToolResult
from kosmos.intelligence.tools.models import FrozenJSON

_IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_SUPPORTED_EFFORTS = frozenset(
    {EffortLevel.INSTANT, EffortLevel.LOW, EffortLevel.MEDIUM, EffortLevel.HIGH}
)


class BenchmarkCategory(str, Enum):
    """Explicit evaluation categories used by the Stage 01.8 suites."""

    PERSONALITY = "personality"
    CONVERSATION = "conversation"
    TOOL_CALLING = "tool_calling"
    ACCURACY = "accuracy"
    REASONING = "reasoning"
    SECURITY = "security"
    CONTEXT = "context"
    STABILITY = "stability"
    PERFORMANCE = "performance"


class EvaluationStrategy(str, Enum):
    """Supported evidence strategies without an external model judge."""

    MANUAL_REVIEW = "manual_review"
    TEXT_HEURISTIC = "text_heuristic"
    TOOL_RESULT = "tool_result"
    NO_TOOL_EXECUTION = "no_tool_execution"
    COMPLETION = "completion"


class BenchmarkStatus(str, Enum):
    """Terminal classifications kept separate in reports."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ExecutionMode(str, Enum):
    """Explicit result provenance, independent from inference authorization."""

    LIVE = "LIVE"
    SIMULATED = "SIMULATED"


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """One validated independent scenario, optionally containing multiple turns."""

    identifier: str
    category: BenchmarkCategory
    description: str
    messages: tuple[str, ...]
    effort: EffortLevel
    strategy: EvaluationStrategy
    selected_tools: tuple[str, ...] = ()
    authorized_tools: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    expected_tool: str | None = None
    expected_value: int | float | None = None
    critical: bool = False
    streaming: bool = False
    expected_arguments: Mapping[str, FrozenJSON] | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier, "scenario identifier")

        if not isinstance(self.category, BenchmarkCategory):
            raise TypeError("category must be a BenchmarkCategory")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be non-empty text")

        if isinstance(self.messages, str | bytes) or not isinstance(self.messages, Sequence):
            raise TypeError("messages must be a sequence of text")

        messages = tuple(self.messages)
        if not messages or not all(isinstance(item, str) and item.strip() for item in messages):
            raise ValueError("messages must contain non-empty text")
        if self.effort not in _SUPPORTED_EFFORTS:
            raise ValueError("scenario effort must be instant, low, medium, or high")
        if not isinstance(self.strategy, EvaluationStrategy):
            raise TypeError("strategy must be an EvaluationStrategy")

        selected = _validate_names(self.selected_tools, "selected tools")
        authorized = _validate_names(self.authorized_tools, "authorized tools")
        terms = tuple(self.required_terms)
        if not all(isinstance(term, str) and term.strip() for term in terms):
            raise ValueError("required terms must contain non-empty text")
        if self.expected_tool is not None:
            _validate_identifier(self.expected_tool, "expected tool")
        if self.strategy is EvaluationStrategy.TOOL_RESULT and (
            self.expected_tool is None or self.expected_value is None
        ):
            raise ValueError("tool-result scenarios require an expected tool and value")
        if self.strategy is EvaluationStrategy.TOOL_RESULT and (
            self.expected_tool not in selected or self.expected_tool not in authorized
        ):
            raise ValueError("the expected tool must be selected and authorized")
        if self.strategy is EvaluationStrategy.TOOL_RESULT and self.expected_arguments is None:
            raise ValueError("tool-result scenarios require expected arguments")
        if self.expected_arguments is not None:
            if self.expected_tool is None:
                raise ValueError("expected arguments require an expected tool")

            expected_arguments = ToolCall(
                "expected_call",
                self.expected_tool,
                self.expected_arguments,
            ).arguments
            object.__setattr__(self, "expected_arguments", expected_arguments)
        if self.strategy is EvaluationStrategy.TEXT_HEURISTIC and not terms:
            raise ValueError("text-heuristic scenarios require factual markers")
        if self.expected_value is not None and (
            isinstance(self.expected_value, bool)
            or not isinstance(self.expected_value, int | float)
            or not math.isfinite(self.expected_value)
        ):
            raise ValueError("expected value must be a finite number")
        if not isinstance(self.critical, bool) or not isinstance(self.streaming, bool):
            raise TypeError("critical and streaming must be booleans")
        if self.streaming and selected:
            raise ValueError("streaming scenarios cannot select structured tools")

        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "selected_tools", selected)
        object.__setattr__(self, "authorized_tools", authorized)
        object.__setattr__(self, "required_terms", terms)


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Validated sampling controls for one explicitly authorized live run."""

    suite: str
    model: str
    repetitions: int = 1
    warmup_runs: int = 0

    def __post_init__(self) -> None:
        if self.suite not in {"quick", "full", "performance"}:
            raise ValueError("suite must be quick, full, or performance")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be non-empty text")
        _validate_count(self.repetitions, "repetitions", minimum=1)
        _validate_count(self.warmup_runs, "warmup_runs", minimum=0)


@dataclass(frozen=True, slots=True)
class PerformanceEvidence:
    """Measured scenario timings and provider metrics without invented values."""

    elapsed_seconds: float
    first_text_seconds: float | None = None
    inference_metrics: tuple[InferenceMetrics, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.elapsed_seconds, bool)
            or not isinstance(self.elapsed_seconds, int | float)
            or not math.isfinite(self.elapsed_seconds)
        ):
            raise ValueError("elapsed_seconds must be finite")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must not be negative")
        if self.first_text_seconds is not None and (
            isinstance(self.first_text_seconds, bool)
            or not isinstance(self.first_text_seconds, int | float)
            or not math.isfinite(self.first_text_seconds)
            or self.first_text_seconds < 0
        ):
            raise ValueError("first_text_seconds must be a finite non-negative number")

        metrics = tuple(self.inference_metrics)
        if not all(isinstance(item, InferenceMetrics) for item in metrics):
            raise TypeError("inference_metrics must contain InferenceMetrics")
        object.__setattr__(self, "inference_metrics", metrics)


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """One measured scenario repetition and its auditable evidence."""

    scenario_id: str
    category: BenchmarkCategory
    repetition: int
    warmup: bool
    status: BenchmarkStatus
    response: str | None
    reason: str
    checks: tuple[str, ...] = ()
    orchestration_metrics: OrchestrationMetrics | None = None
    performance: PerformanceEvidence | None = None
    tool_results: tuple[ToolResult, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkMetadata:
    """Non-personal environment metadata required to interpret one run."""

    kosmos_version: str
    model: str
    model_digest: str | None
    ollama_version: str | None
    execution_mode: ExecutionMode
    python_version: str
    operating_system: str
    context_length: int
    effort_policies: Mapping[str, Mapping[str, int | float | bool]]
    repetitions: int
    warmup_runs: int
    scenario_version: str
    started_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.execution_mode, ExecutionMode):
            raise TypeError("execution_mode must be an ExecutionMode")

        policies = {
            name: MappingProxyType(dict(values)) for name, values in self.effort_policies.items()
        }
        object.__setattr__(self, "effort_policies", MappingProxyType(policies))


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """Complete live run; warm-ups remain visible but excluded from summaries."""

    config: BenchmarkConfig
    metadata: BenchmarkMetadata
    results: tuple[ScenarioResult, ...]


def _validate_identifier(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a snake_case identifier")


def _validate_names(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str | bytes) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence")

    names = tuple(values)
    for name in names:
        _validate_identifier(name, field_name)
    if len(names) != len(set(names)):
        raise ValueError(f"{field_name} must be unique")
    return names


def _validate_count(value: object, field_name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
