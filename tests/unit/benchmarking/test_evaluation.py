"""Evidence classification tests."""

from kosmos.benchmarking.evaluation import evaluate
from kosmos.benchmarking.models import (
    BenchmarkCategory,
    BenchmarkScenario,
    BenchmarkStatus,
    EvaluationStrategy,
)
from kosmos.core.orchestration import EffortLevel, OrchestrationStatus
from kosmos.intelligence.tools import ToolCall, ToolResult, ToolResultStatus


def _scenario(strategy: EvaluationStrategy) -> BenchmarkScenario:
    tools = ("calculate",) if strategy is EvaluationStrategy.TOOL_RESULT else ()
    return BenchmarkScenario(
        "evaluation_case",
        BenchmarkCategory.TOOL_CALLING,
        "Evaluation case",
        ("Prompt",),
        EffortLevel.LOW,
        strategy,
        selected_tools=tools,
        authorized_tools=tools,
        expected_tool="calculate" if strategy is EvaluationStrategy.TOOL_RESULT else None,
        expected_value=4000 if strategy is EvaluationStrategy.TOOL_RESULT else None,
        expected_arguments=(
            {"operation": "multiply", "a": 125, "b": 32}
            if strategy is EvaluationStrategy.TOOL_RESULT
            else None
        ),
    )


def test_manual_review_is_not_counted_as_a_deterministic_pass() -> None:
    result = evaluate(
        _scenario(EvaluationStrategy.MANUAL_REVIEW),
        orchestration_status=OrchestrationStatus.COMPLETED,
        response="Natural response",
        tool_results=(),
    )

    assert result.status is BenchmarkStatus.MANUAL_REVIEW


def test_tool_selection_execution_and_communication_are_separate_checks() -> None:
    tool_call = ToolCall(
        "call-1",
        "calculate",
        {"operation": "multiply", "a": 125, "b": 32},
    )
    tool_result = ToolResult(
        "call-1",
        "calculate",
        ToolResultStatus.SUCCESS,
        {"result": 4000},
    )

    passed = evaluate(
        _scenario(EvaluationStrategy.TOOL_RESULT),
        orchestration_status=OrchestrationStatus.COMPLETED,
        response="O resultado é 4.000.",
        tool_results=(tool_result,),
        tool_calls=(tool_call,),
    )
    failed = evaluate(
        _scenario(EvaluationStrategy.TOOL_RESULT),
        orchestration_status=OrchestrationStatus.COMPLETED,
        response="O resultado é 5.",
        tool_results=(tool_result,),
        tool_calls=(tool_call,),
    )

    assert passed.status is BenchmarkStatus.PASS
    assert failed.status is BenchmarkStatus.FAIL
    assert failed.checks[-1] == "response communicated result: False"


def test_correct_text_and_value_do_not_hide_incorrect_tool_arguments() -> None:
    wrong_call = ToolCall(
        "call-1",
        "calculate",
        {"operation": "multiply", "a": 100, "b": 40},
    )
    result = evaluate(
        _scenario(EvaluationStrategy.TOOL_RESULT),
        orchestration_status=OrchestrationStatus.COMPLETED,
        response="O resultado é 4.000.",
        tool_results=(
            ToolResult("call-1", "calculate", ToolResultStatus.SUCCESS, {"result": 4000}),
        ),
        tool_calls=(wrong_call,),
    )

    assert result.status is BenchmarkStatus.FAIL
    assert "arguments matched: False" in result.checks


def test_controlled_orchestration_failure_is_an_error() -> None:
    result = evaluate(
        _scenario(EvaluationStrategy.COMPLETION),
        orchestration_status=OrchestrationStatus.CONTEXT_LIMIT,
        response=None,
        tool_results=(),
    )

    assert result.status is BenchmarkStatus.ERROR


def test_untrusted_text_requires_absence_of_tool_execution_evidence() -> None:
    result = evaluate(
        _scenario(EvaluationStrategy.NO_TOOL_EXECUTION),
        orchestration_status=OrchestrationStatus.COMPLETED,
        response="Text only",
        tool_results=(),
    )

    assert result.status is BenchmarkStatus.PASS
    assert result.checks == ("tool results: 0",)
