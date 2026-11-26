# Personality Engine

## Implementation status

Stage 01.4 implements and automatically tests a provider-independent representation of the Kosmos
identity, immutable communication profiles, permanent principles, and deterministic system
instructions. The work is on `feature/personality-engine` pending maintainer review and integration.
Real response quality and adherence by Qwen on Ubuntu remain unvalidated.

The official behavioral and future voice direction is defined in
[Kosmos Personality Specification](PERSONALITY-SPECIFICATION.md). This document describes its
software representation.

## Responsibilities and boundaries

The package `kosmos.intelligence.personality`:

- exposes the official immutable identity;
- validates structured profile fields;
- maps trait ranges to semantically distinct guidance;
- preserves permanent principles for every valid profile; and
- builds compact deterministic text suitable for the existing `SYSTEM` role.

It does not infer, call providers, execute or authorize tools, read user files, persist settings,
log personal data, access a network, synthesize voice, or accept arbitrary text as system-level
configuration. It has no Ollama, HTTPX, Qwen, audio, GPU, endpoint, or model dependency.

## Package structure

```text
src/kosmos/intelligence/personality/
├── __init__.py
├── engine.py
├── identity.py
├── models.py
└── principles.py
```

- `identity.py` owns `AssistantIdentity` and the official `KOSMOS_IDENTITY` value.
- `models.py` owns `PersonalityProfile` and structured-field validation.
- `principles.py` owns immutable permanent and contextual guidance.
- `engine.py` owns trait translation and deterministic instruction assembly.
- `__init__.py` defines the public package surface.

No interface, factory, repository, service locator, or persistence layer is needed for this
deterministic standard-library behavior.

## Public contracts

```python
from kosmos.intelligence.personality import (
    AssistantIdentity,
    KOSMOS_IDENTITY,
    PERMANENT_PRINCIPLES,
    PersonalityEngine,
    PersonalityProfile,
)
```

`AssistantIdentity` and `PersonalityProfile` are frozen, slotted dataclasses.
`PersonalityEngine(profile=None)` accepts a validated profile or creates the approved default.
`profile` returns that immutable profile. `build_system_instruction()` accepts no user content and
returns the complete instruction.

### Default API example

```python
from kosmos.intelligence.personality import PersonalityEngine

personality = PersonalityEngine()
system_instruction = personality.build_system_instruction()
```

### Custom profile example

```python
from kosmos.intelligence.personality import PersonalityEngine, PersonalityProfile

profile = PersonalityProfile(
    formality=50,
    humor=10,
    detail_level=85,
    preferred_language="en-US",
    honorific=None,
)
system_instruction = PersonalityEngine(profile).build_system_instruction()
```

New sessions may use a new profile. Stage 01.4 intentionally does not mutate the personality of an
active session.

## Validation

All eight traits must be real integers in the inclusive range `0..100`; booleans are rejected even
though Python treats them as integers. The language is a compact structured language tag with a
35-character maximum. The honorific is either `None` or a single trimmed title of at most 24
characters containing letters and limited title punctuation. Empty, multiline, spaced,
control-like, or instruction-shaped values are rejected rather than concatenated into a system
instruction.

The default values are:

```python
PersonalityProfile(
    formality=65,
    directness=85,
    humor=40,
    sarcasm=25,
    proactivity=85,
    assertiveness=80,
    emotional_expressiveness=35,
    detail_level=60,
    preferred_language="pt-BR",
    honorific="senhor",
)
```

## Trait translation

Each trait uses deterministic inclusive ranges:

- `0..33`: low guidance;
- `34..66`: medium guidance; and
- `67..100`: high guidance.

Every range selects different natural-language guidance. The values are not probabilities. Traits
remain independent so, for example, high directness can coexist with high detail. Permanent
principles and critical-situation rules override stylistic humor or sarcasm guidance where the two
would conflict.

## System instruction construction

The builder assembles six stable sections in this order:

1. official identity and purpose;
2. preferred language and honorific;
3. selected guidance for all eight traits;
4. contextual adaptation;
5. permanent honesty, safety, privacy, integrity, and identity principles; and
6. deterministic execution and untrusted-content boundaries.

It uses no templates from external packages, inference, random values, timestamps, runtime model
data, or caller-provided arbitrary instruction fragments. Equal profiles therefore produce exactly
equal strings. Principles are never truncated to meet the engineering budget.

The current default instruction is below 2,000 characters. The existing `ContextPolicy` default is
6,000 content characters, leaving more than 4,000 characters for the current user message and
eligible confirmed history. Character counts are an engineering proxy, not model-specific token
counts.

## Conversation Engine integration

The Personality Engine composes with the existing explicit system-instruction boundary; neither
`ConversationEngine` nor `LLMProvider` is changed:

```python
import asyncio

from kosmos.intelligence.conversation import ConversationEngine
from kosmos.intelligence.models import InferenceResponse
from kosmos.intelligence.personality import PersonalityEngine
from tests.fakes.llm_provider import FakeLLMProvider


async def main() -> None:
    provider = FakeLLMProvider(
        response=InferenceResponse(model="test-model", content="Certamente, senhor.")
    )
    conversation = ConversationEngine(provider)
    instruction = PersonalityEngine().build_system_instruction()
    session = conversation.create_session(system_instruction=instruction)

    await conversation.generate(session.session_id, "Podemos começar?", model="test-model")

    request = provider.requests[0]
    assert request.messages[0].content == instruction


asyncio.run(main())
```

`ContextPolicy` places the system message first, followed by the newest complete historical turns
that fit and the current user message. The instruction is stored separately from confirmed history,
survives history clearing, works for complete and streaming inference, and remains isolated by
session. Building it performs no provider call, so one conversation turn still produces exactly
one inference request. Personality is explicit and is not imposed globally on specialized future
inference tasks.

The example is deterministic and network-free. It validates request composition, not real model
behavior.

## Security and privacy

Only validated application configuration enters the instruction. User messages, retrieved data,
external results, and other untrusted text remain ordinary conversation data and cannot be promoted
through this API. The engine has no persistence, telemetry, network, command, file, authorization,
or audio capability and introduces no new dependency.

Language-model instructions are not an enforcement mechanism and cannot guarantee resistance to
prompt injection or faithful behavior from a small model. Deterministic software remains
responsible for argument validation, permissions, authorization, execution, and evidence of
results:

> The AI interprets intent. The software validates and executes operations.

## Limitations

- Automated tests use fake providers and do not validate Qwen personality adherence.
- The 2,000-character target and three trait ranges are provisional engineering choices.
- No tokenization, context-window change, additional tone inference, user account, persistence,
  dynamic active-session update, GUI, voice, tool execution, memory, or monitoring is implemented.
- Voice identity, Razo, and Piper are documentation-only Stage 02 candidates with unresolved
  technical and licensing review.

