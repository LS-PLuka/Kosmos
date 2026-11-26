# Institutional Knowledge

## Status and purpose

R2 — Institutional Knowledge adds a compact trusted representation of facts defined by the Kosmos
project. It lets conversational sessions distinguish product identity, creator, current
capabilities, operational state, and future plans without inference, network access, retrieval, or
runtime file loading.

The implementation is deterministic and automatically tested. Tests prove data and request
composition, not that a real model follows the instruction. Renewed Qwen validation on Ubuntu
remains pending, so Stage 01 is not definitively validated.

## Trusted source and contract

`kosmos.intelligence.personality.knowledge` owns the frozen, slotted
`InstitutionalKnowledge` value and `KOSMOS_INSTITUTIONAL_KNOWLEDGE`. It references
`KOSMOS_IDENTITY` instead of duplicating the product name, slogan, or purpose. Its remaining fields
contain the approved developer, name origin, architectural principles, implemented capability
facts, current limitations, and planned capability facts. Each immutable `CapabilityFact` keeps a
detailed description beside its compact prompt label.

The value uses only immutable nested contracts and tuples. `build_instruction()` performs a pure,
deterministic transformation into compact English guidance. It has no provider, model, endpoint,
network, database, environment, operating-system identity, or conversation dependency and causes
no import-time side effects.

## Official facts

Pedro Luka developed Kosmos and chose its name during project conception. No date, official
philosophical meaning, undocumented motivation, or additional creator is asserted. Kosmos remains a
personal AI assistant and intellectual partner; behavioral references such as JARVIS, Alfred,
Vision, FRIDAY, and TARS do not replace its identity.

The architecture is local-first, modular, extensible, provider-independent, privacy-oriented,
explicitly authorized, and deterministic. The permanent execution boundary remains:

> The AI interprets intent. The software validates and executes operations.

External processing remains optional and explicitly authorized. No silent or paid fallback is
introduced, and local operation does not imply that hardware or electricity has no cost.

## Capability states

The structured current categories cover text conversation, generation and streaming, temporary
session context, configurable personality and effort, local inference, authorized pure tools for
basic calculation and counting, and the development CLI. Full behavioral validation remains
pending.

Registration or implementation never proves current availability. A capability may still depend
on effort policy, selected tools, authorization, provider support, and configuration. The runtime
state is authoritative, and institutional knowledge cannot expand it. These states remain distinct:

- **implemented:** software exists in the project;
- **available:** the current runtime can expose it;
- **authorized:** deterministic policy permits its use;
- **executed:** software produced evidence of the operation;
- **validated:** applicable automated or real validation succeeded; and
- **planned:** the roadmap describes future work without a delivery guarantee.

Voice, system control, developer agents, persistent memory, proactive automation, desktop GUI,
web and external integrations, and multimodal intelligence are planned, not current. The assistant
may say “Ainda não” or explain that a capability is planned. It must not say it can never exist,
invent a schedule, guarantee delivery, or claim it already operated.

## Creator, user, and authorization

Knowing that Pedro Luka is the developer does not identify the current user. A name voluntarily
provided in a conversation may be used only as temporary conversational context. It does not verify
identity, prove that the user is the developer, persist a profile, alter trusted facts, enable a
tool, lower risk, or grant permission.

Institutional knowledge is not personal memory, RAG, a vector store, user database, authentication,
authorization, or conversation history. User content and tool output remain untrusted data and
cannot overwrite the institutional value or the permanent principles.

## System-instruction composition

`CoreOrchestrator.create_session()` builds the R1 personality instruction, builds the institutional
instruction, and joins them with one newline. Conceptually, the result contains identity,
personality, permanent principles, institutional facts, and capability boundaries. The existing
Conversation Engine stores it separately from history, places it first in complete, streaming, and
tool-calling requests, preserves it across `clear_session()`, and isolates it per session.

No additional inference retrieves these facts. Custom personality profiles alter only their
behavioral component; the institutional source remains the same.

## Character budget

For the approved default profile:

| Component | Characters |
| --- | ---: |
| R1 personality | 1,982 |
| R2 institutional knowledge | 611 |
| Joining newline | 1 |
| Complete system instruction | 2,594 |
| Remaining within former `ContextPolicy(6000)` | 3,406 |
| Remaining within R3 `ContextPolicy(8000)` | 5,406 |

R2 therefore adds 612 characters to the R1 system instruction while remaining below the provisional
2,600-character target. These are exact Python character counts for the current strings, not token
counts or guarantees about model context retention.

## Update lifecycle and limitations

Maintainers update the frozen value and this documentation when an approved roadmap stage changes
real product facts. Each update must keep current and planned states separate, preserve provider
independence and authorization boundaries, review the prompt budget, and add deterministic tests.
Runtime YAML, JSON, databases, generic knowledge management, and dynamic loaders are intentionally
out of scope.

R2 adds no memory, authentication, authorization, provider, tool, routing, effort-policy change,
voice, system control, web access, GUI, or dependency. R3 changes context policy separately while
preserving this institutional instruction byte-for-byte. R4–R6 remain separate future refinement
work.
