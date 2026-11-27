"""Tests for trusted provider-independent institutional knowledge."""

from dataclasses import FrozenInstanceError, replace

import pytest

from kosmos.intelligence.personality import (
    KOSMOS_IDENTITY,
    KOSMOS_INSTITUTIONAL_KNOWLEDGE,
    InstitutionalKnowledge,
    PersonalityEngine,
)


def test_official_identity_and_developer_share_one_trusted_source() -> None:
    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE

    assert knowledge.identity is KOSMOS_IDENTITY
    assert knowledge.identity.name == "Kosmos"
    assert knowledge.identity.slogan == "The intelligence orbiting your world."
    assert knowledge.developer == "Pedro Luka"
    assert knowledge.name_origin == "during project conception"


def test_knowledge_and_nested_collections_are_immutable() -> None:
    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE

    with pytest.raises(FrozenInstanceError):
        knowledge.developer = "Someone else"  # type: ignore[misc]

    assert isinstance(knowledge.architecture_principles, tuple)
    assert isinstance(knowledge.implemented_capabilities, tuple)
    assert isinstance(knowledge.current_limitations, tuple)
    assert isinstance(knowledge.planned_capabilities, tuple)


def test_current_and_planned_capabilities_are_distinct() -> None:
    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE

    implemented = " ".join(item.description for item in knowledge.implemented_capabilities)
    planned = " ".join(item.description for item in knowledge.planned_capabilities)

    assert "natural-language interpretation" in implemented
    assert "text streaming" in implemented
    assert "Temporary context" in implemented
    assert "basic mathematics and item counting" in implemented
    assert "system control" not in implemented
    assert "Stage 02 voice interaction" in planned
    assert "Stage 03 authorized system control" in planned
    assert "Stage 05 persistent memory" in planned
    assert "Stage 08 web intelligence" in planned


def test_current_limitations_cover_unimplemented_runtime_categories() -> None:
    limitations = " ".join(KOSMOS_INSTITUTIONAL_KNOWLEDGE.current_limitations)

    assert "voice recognition" in limitations
    assert "operating-system control" in limitations
    assert "arbitrary command execution" in limitations
    assert "persistent memory" in limitations
    assert "internet research" in limitations
    assert "multimodal processing" in limitations


def test_instruction_distinguishes_developer_user_and_operational_states() -> None:
    instruction = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()

    assert "Creator != user" in instruction
    assert "names grant no identity/memory/permission" in instruction
    assert "Implemented != available/authorized/executed/validated" in instruction
    assert "trust runtime" in instruction
    assert "Future:" in instruction
    assert "say not yet/planned, not never" in instruction


def test_instruction_preserves_architecture_and_authorization_boundaries() -> None:
    instruction = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()

    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE

    for principle in knowledge.architecture_principles[:4]:
        assert principle in instruction

    assert "privacy-by-design" in instruction
    assert "explicit authorization" in instruction
    assert "deterministic execution" in instruction
    assert "external use opt-in" in instruction
    assert "no paid fallback" in instruction


def test_instruction_is_deterministic_compact_and_side_effect_free() -> None:
    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE

    first = knowledge.build_instruction()
    second = knowledge.build_instruction()

    assert first == second
    assert len(first) <= 617


def test_complete_system_instruction_preserves_the_conversation_budget() -> None:
    personality = PersonalityEngine().build_system_instruction()
    knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()
    complete = "\n".join((personality, knowledge))

    assert len(personality) <= 2000
    assert len(complete) <= 2600
    assert 6000 - len(complete) >= 3400


@pytest.mark.parametrize("forbidden", ["Ollama", "Qwen", "qwen3.5", "GPU", "api_key"])
def test_instruction_is_provider_independent(forbidden: str) -> None:
    assert forbidden not in KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()


def test_replacing_facts_creates_a_separate_immutable_value() -> None:
    original = KOSMOS_INSTITUTIONAL_KNOWLEDGE
    changed = replace(original, developer="Another developer")

    assert isinstance(changed, InstitutionalKnowledge)
    assert changed is not original
    assert original.developer == "Pedro Luka"
