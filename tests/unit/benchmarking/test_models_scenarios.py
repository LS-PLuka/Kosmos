"""Scenario contract and suite-selection tests."""

import pytest

from kosmos.benchmarking.models import (
    BenchmarkCategory,
    BenchmarkConfig,
    BenchmarkScenario,
    EvaluationStrategy,
)
from kosmos.benchmarking.scenarios import SCENARIO_VERSION, list_scenarios, select_suite
from kosmos.core.orchestration import EffortLevel


def test_scenario_contract_is_immutable_and_validated() -> None:
    scenario = BenchmarkScenario(
        "valid_case",
        BenchmarkCategory.ACCURACY,
        "A valid case",
        ("Fictional prompt",),
        EffortLevel.LOW,
        EvaluationStrategy.COMPLETION,
    )

    with pytest.raises(AttributeError):
        scenario.identifier = "changed"  # type: ignore[misc]

    with pytest.raises(ValueError, match="snake_case"):
        BenchmarkScenario(
            "Invalid case",
            BenchmarkCategory.ACCURACY,
            "Invalid identifier",
            ("Prompt",),
            EffortLevel.LOW,
            EvaluationStrategy.COMPLETION,
        )

    with pytest.raises(TypeError, match="sequence"):
        BenchmarkScenario(
            "invalid_messages",
            BenchmarkCategory.ACCURACY,
            "Invalid messages",
            "Prompt",  # type: ignore[arg-type]
            EffortLevel.LOW,
            EvaluationStrategy.COMPLETION,
        )


def test_tool_scenario_requires_explicit_expected_evidence() -> None:
    with pytest.raises(ValueError, match="expected tool and value"):
        BenchmarkScenario(
            "missing_evidence",
            BenchmarkCategory.TOOL_CALLING,
            "Missing expected value",
            ("Prompt",),
            EffortLevel.LOW,
            EvaluationStrategy.TOOL_RESULT,
            selected_tools=("calculate",),
            authorized_tools=("calculate",),
        )

    with pytest.raises(ValueError, match="expected arguments"):
        BenchmarkScenario(
            "missing_arguments",
            BenchmarkCategory.TOOL_CALLING,
            "Missing expected arguments",
            ("Prompt",),
            EffortLevel.LOW,
            EvaluationStrategy.TOOL_RESULT,
            selected_tools=("calculate",),
            authorized_tools=("calculate",),
            expected_tool="calculate",
            expected_value=3,
        )


def test_named_suites_are_stable_unique_and_cover_required_categories() -> None:
    catalog = list_scenarios()
    assert SCENARIO_VERSION == "1.2"
    assert len({item.identifier for item in catalog}) == len(catalog)
    assert len(select_suite("quick")) == 7
    assert {item.category for item in select_suite("full")} >= {
        BenchmarkCategory.PERSONALITY,
        BenchmarkCategory.CONVERSATION,
        BenchmarkCategory.TOOL_CALLING,
        BenchmarkCategory.ACCURACY,
        BenchmarkCategory.REASONING,
        BenchmarkCategory.SECURITY,
        BenchmarkCategory.CONTEXT,
        BenchmarkCategory.STABILITY,
    }
    assert all(
        item.category is BenchmarkCategory.PERFORMANCE for item in select_suite("performance")
    )


def test_performance_suite_can_be_filtered_by_configured_effort() -> None:
    selected = select_suite("performance", efforts=(EffortLevel.MEDIUM,))

    assert [item.identifier for item in selected] == ["thinking_medium"]


@pytest.mark.parametrize(
    ("repetitions", "warmups", "error"),
    [(0, 0, ValueError), (True, 0, TypeError), (1, -1, ValueError)],
)
def test_benchmark_config_rejects_invalid_sampling(
    repetitions: int,
    warmups: int,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        BenchmarkConfig("quick", "model", repetitions, warmups)
