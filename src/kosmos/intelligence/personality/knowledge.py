"""Trusted institutional facts used in Kosmos system instructions."""

from dataclasses import dataclass

from kosmos.intelligence.personality.identity import KOSMOS_IDENTITY, AssistantIdentity


@dataclass(frozen=True, slots=True)
class CapabilityFact:
    """One detailed capability fact with a compact system-instruction label."""

    description: str
    instruction_label: str


@dataclass(frozen=True, slots=True)
class InstitutionalKnowledge:
    """Immutable provider-independent facts controlled by the Kosmos project."""

    identity: AssistantIdentity
    developer: str
    name_origin: str
    architecture_principles: tuple[str, ...]
    implemented_capabilities: tuple[CapabilityFact, ...]
    current_limitations: tuple[str, ...]
    planned_capabilities: tuple[CapabilityFact, ...]

    def build_instruction(self) -> str:
        """Build a compact deterministic instruction from trusted facts."""

        current = ", ".join(item.instruction_label for item in self.implemented_capabilities)
        planned = ", ".join(item.instruction_label for item in self.planned_capabilities)
        architecture = "/".join(self.architecture_principles[:4])
        privacy = self.architecture_principles[4].replace(" ", "-")

        return (
            f"Origin: {self.developer} developed and named {self.identity.name} "
            f"{self.name_origin}; invent no details. Creator != user; names grant no "
            f"identity/memory/permission. Current: {current}. "
            "Implemented != available/authorized/executed/validated; trust runtime. "
            f"Future: {planned}; say not yet/planned, not never. Design: {architecture}, "
            f"{privacy}, explicit authorization, deterministic execution; external use opt-in/no "
            "paid fallback."
        )


KOSMOS_INSTITUTIONAL_KNOWLEDGE = InstitutionalKnowledge(
    identity=KOSMOS_IDENTITY,
    developer="Pedro Luka",
    name_origin="during project conception",
    architecture_principles=(
        "local-first",
        "modular",
        "extensible",
        "provider-independent",
        "privacy by design",
        "explicit authorization",
        "deterministic execution",
    ),
    implemented_capabilities=(
        CapabilityFact(
            "Text conversation, natural-language interpretation, analysis and explanation of "
            "supplied information, text generation, and text streaming",
            "text/streaming",
        ),
        CapabilityFact("Temporary context within one session", "context"),
        CapabilityFact(
            "Configurable personality and Instant, Low, Medium, and High effort levels",
            "personality/effort",
        ),
        CapabilityFact("Local inference integration", "local AI"),
        CapabilityFact(
            "Authorized pure tools for basic mathematics and item counting",
            "authorized pure tools",
        ),
        CapabilityFact("Terminal development interface", "CLI"),
    ),
    current_limitations=(
        "voice recognition, synthesis, and wake word",
        "operating-system control and application opening",
        "file management and arbitrary command execution",
        "functional Codex or Claude Code integration",
        "persistent memory and user database",
        "proactive monitoring and automation",
        "graphical interface",
        "internet research and external integrations",
        "computer vision and multimodal processing",
    ),
    planned_capabilities=(
        CapabilityFact("Stage 02 voice interaction", "voice"),
        CapabilityFact("Stage 03 authorized system control", "system control"),
        CapabilityFact("Stage 04 developer agents", "dev agents"),
        CapabilityFact("Stage 05 persistent memory", "memory"),
        CapabilityFact("Stage 06 proactive intelligence", "automation"),
        CapabilityFact("Stage 07 desktop experience", "GUI"),
        CapabilityFact("Stage 08 web intelligence and external integrations", "web/integrations"),
        CapabilityFact("Stage 09 multimodal intelligence", "multimodal"),
    ),
)
