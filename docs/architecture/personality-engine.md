# Personality Engine

## Implementation status

The provider-independent Personality Engine is integrated into the Stage 01 Core Engine. R1 —
Personality & Communication refines its defaults and deterministic instruction after the first real
Ubuntu validation. Automated coverage is complete for the software contracts, but real Qwen
behavior under the revised prompt still requires renewed Ubuntu validation.

The official direction is defined in
[Kosmos Personality Specification](PERSONALITY-SPECIFICATION.md).

## Responsibilities and boundaries

The package `kosmos.intelligence.personality`:

- exposes the immutable `AssistantIdentity` and `KOSMOS_IDENTITY`;
- exposes immutable institutional facts without duplicating the official identity;
- validates immutable `PersonalityProfile` values;
- translates qualitative trait ranges into distinct instructions;
- preserves `PERMANENT_PRINCIPLES` for every profile; and
- builds one compact deterministic system instruction.

It performs no inference, persistence, network access, logging, authorization, tool execution,
command execution, memory operation, or voice processing. It has no provider, model, endpoint,
hardware, or transport dependency and accepts no conversation content as configuration.

## Package structure

```text
src/kosmos/intelligence/personality/
├── __init__.py
├── engine.py
├── identity.py
├── knowledge.py
├── models.py
└── principles.py
```

`identity.py` owns the official identity, `knowledge.py` references that identity and owns trusted
institutional facts, `models.py` owns validated configuration, `principles.py` owns permanent and
contextual guidance, and `engine.py` owns deterministic trait translation and assembly. No
additional interface, factory, repository, or service layer is needed.

## Public contracts

```python
from kosmos.intelligence.personality import (
    AssistantIdentity,
    CapabilityFact,
    InstitutionalKnowledge,
    KOSMOS_IDENTITY,
    KOSMOS_INSTITUTIONAL_KNOWLEDGE,
    PERMANENT_PRINCIPLES,
    PersonalityEngine,
    PersonalityProfile,
)
```

`AssistantIdentity` and `PersonalityProfile` remain frozen, slotted dataclasses.
`PersonalityEngine(profile=None)` accepts only a validated profile or builds the approved default.
The `profile` property returns that immutable value. `build_system_instruction()` accepts no user
content and returns the complete instruction.

## Approved defaults

```python
PersonalityProfile(
    formality=45,
    directness=90,
    humor=45,
    sarcasm=25,
    proactivity=85,
    assertiveness=80,
    emotional_expressiveness=45,
    detail_level=40,
    preferred_language="pt-BR",
    honorific="senhor",
)
```

All traits remain real integers in the inclusive range `0..100`; booleans and non-integers are
rejected. Language tags and honorifics retain their existing structured validation. An honorific
may be customized or disabled with `None`.

## Trait translation

The existing inclusive qualitative ranges remain:

- `0..33`: low guidance;
- `34..66`: medium guidance; and
- `67..100`: high guidance.

The text for each range now emphasizes modern natural language, proportional detail, selective
proactivity, respectful disagreement, and situational humor. Extreme profiles continue to produce
distinct instructions. A narrow zero-value override makes `sarcasm=0` disable sarcasm and irony;
values `1..33`, including the default `25`, permit rare mild dry irony in suitable low-risk
contexts. No additional scale or probabilistic behavior is introduced.

## Instruction construction

The builder emits six stable sections:

1. identity and purpose;
2. language and honorific;
3. selected trait guidance;
4. contextual proportionality;
5. permanent principles; and
6. execution and untrusted-content boundaries.

Equal profiles produce equal strings. The builder uses no random values, timestamps, provider
state, external templates, or caller-provided instruction fragments.

The previous default instruction contained **1,990 characters**. The unchanged R1 personality
component contains **1,982 characters**, a reduction of 8 characters (about 0.40%). The largest
behavioral changes
are selective proactivity, concise-by-default detail, natural language, rare low-risk dry irony,
contextual handling of shared information, and explicit prohibition of unsupported operational
claims. These changes reuse the existing budget instead of increasing it.

The R2 institutional component contains **611 characters**. The newline-composed system instruction
contains **2,594 characters**, 612 more than R1 alone, and leaves **3,406 characters** of the
6,000-character `ContextPolicy` budget for the current message and eligible history. Character
counts are deterministic engineering measures, not exact token counts.

## Conversation integration

The Personality Engine continues to compose with the existing explicit system-instruction
boundary. Neither `ConversationEngine`, `ContextPolicy`, nor `LLMProvider` changes:

```python
from kosmos.intelligence.conversation import ConversationEngine
from kosmos.intelligence.personality import PersonalityEngine

personality = PersonalityEngine().build_system_instruction()
knowledge = KOSMOS_INSTITUTIONAL_KNOWLEDGE.build_instruction()
instruction = "\n".join((personality, knowledge))
conversation = ConversationEngine(provider)
session = conversation.create_session(system_instruction=instruction)
```

The composed system instruction remains first in complete, streaming, and tool-calling requests. It is
stored separately from confirmed history, survives `clear_session()`, and remains isolated between
sessions. Building it performs no inference, so a user turn still produces only the inference calls
defined by the existing conversation and orchestration flows.

## Security and operational honesty

Only validated structured configuration enters the system instruction. Conversation messages,
retrieved content, and tool results remain untrusted data. Behavioral text never grants permission:

> The AI interprets intent. The software validates and executes operations.

The instruction allows voluntarily shared information to be used in the current conversation
without implying identity verification, persistence, disclosure permission, external processing,
or operational authorization. It requires evidence before claiming execution and prohibits
invented memory, checks, monitoring, capabilities, or operations. Existing deterministic tool
validation and authorization remain unchanged.

## Testing and limitations

Tests cover defaults, immutability, validation, deterministic construction, qualitative range
distinction, proportionality, natural language, custom languages and honorifics, disabled
honorifics, humor, sarcasm zero behavior, selective proactivity, permanent principles, contextual
information versus authorization, operational honesty, prompt budget, complete inference,
streaming, session isolation, and persistence across `clear_session()`.

Fake providers validate request composition, not generated personality. R1 performs no real
inference and changes no generation limit, `num_ctx`, model, provider, conversation policy, effort
policy, tool routing, authorization mechanism, persistent memory, voice system, or dependency.
Renewed real Ubuntu validation is required before claiming the behavioral refinement is validated.
