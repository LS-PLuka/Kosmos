# Intelligence Architecture

## Status and scope

This document records the intelligence architecture beyond the completed Stage 01.1 Core
Foundation. The Stage 01.2 Ollama HTTP adapter is implemented and automatically tested with
simulated transports, but real inference on the target Ubuntu host remains pending. Stage 01.3
in-memory conversation management and Stage 01.4 personality representation are integrated; real
personality behavior validation remains pending. Stage 01.5 tool-calling foundations are
integrated, with real Qwen behavior validation pending. Stage 01.6 core orchestration and effort
policies are integrated and automatically tested. Stage 01.7 provides the development CLI. Stage
01.8 provides benchmark infrastructure and a maintainer-run Ubuntu validation procedure; real Qwen
behavior, performance, and offline validation remain pending. R2 adds deterministic institutional
knowledge to the session instruction. R3 improves temporary session-context selection and
observability without adding persistent memory. External
agents and web intelligence still require separate roadmap stages.

## Hybrid local-first orchestration

Kosmos is a hybrid, local-first personal assistant. The primary intelligence runs locally and is
planned to interpret intent, understand requests, manage conversations, select tools, request
operations, coordinate workflows, delegate specialized work, interpret tool results, and
communicate outcomes.

The model does not directly execute sensitive operations and must not receive unrestricted access
to the operating system or terminal. User intent, authorization, and execution remain separate:

> The AI interprets intent. The software validates and executes operations.

Exact calculations, counts, state checks, validation, authorization, and other deterministic work
belong in Python. LLM output may propose an operation, but software validates its arguments and
policy before any execution.

## Initial local intelligence

The primary provider adapter is Ollama. The initial official runtime model selection is Qwen 3.5
4B with these starting settings:

| Setting | Planned value |
| --- | --- |
| Ollama identifier | `qwen3.5:4b-q4_K_M` |
| Quantization | Q4_K_M |
| Default endpoint | `http://127.0.0.1:11434` |
| Initial context | 4,096 tokens |
| Default thinking | Disabled |
| Advanced thinking | Enabled according to effort level |

The model remains externally configurable and must be selected in each `InferenceRequest`. No
model identifier belongs in business rules, and the provider-independent `LLMProvider` contract
does not expose Ollama-specific details. Model weights are installed separately and are not
included in this repository. See [Ollama Provider](ollama-provider.md) for the implemented adapter.

Ollama presents the selected model as Apache-2.0 licensed. That information must be verified for
the exact model artifact before distribution or incorporation. Separate model weights and their
terms do not change the PolyForm Noncommercial 1.0.0 license of Kosmos.

## Preliminary manual inference observations

The maintainer manually observed the following on the personal Ubuntu system. These are
preliminary observations, not an automated benchmark, a complete model validation, or evidence of
reliable tool calling:

- the Qwen 3.5 model reported approximately 4.2 billion parameters;
- the download was approximately 3.3 GB;
- inference used 100% GPU offload with a 4,096-token context;
- the inference process used approximately 3,744 MiB of VRAM;
- generation was approximately 44–48 tokens per second with thinking disabled;
- simple warmed-model responses took approximately 0.65–2.06 seconds;
- one simple JSON response was produced correctly;
- one technical response contained inaccuracies;
- one arithmetic reasoning test produced an incorrect result; and
- thinking enabled produced excessively long reasoning for a simple request.

These observations reinforce deterministic execution and validation; they do not establish model
reliability.

## Conversational personality boundary

The Stage 01.4 Personality Engine owns Kosmos's conversational identity, validated communication
preferences, permanent behavioral principles, and deterministic system-instruction construction.
It is independent of providers and model identifiers. Application code may pass its output through
the Conversation Engine's existing explicit system-instruction boundary; the personality is not a
global requirement for every internal inference task.

Personality instructions influence model behavior but do not grant authority or provide a security
boundary. They cannot replace deterministic validation, authorization, execution policy, or
evidence of completed work. Real response quality and instruction adherence remain pending for
real Stage 01.8 validation.

## Institutional knowledge boundary

R2 adds one frozen, provider-independent source for approved project facts: official identity,
developer and name origin, architectural principles, implemented capability categories, and future
roadmap categories. `CoreOrchestrator.create_session()` composes its compact instruction after the
R1 personality instruction. The same stored system instruction reaches complete generation,
streaming, and structured tool requests and survives `clear_session()`.

Institutional knowledge is not memory, retrieval, authentication, authorization, or evidence that
a capability is available or an action was executed. A name supplied in conversation remains
temporary unverified context and never identifies the user as the developer. Runtime policy,
selected tools, authorization, provider capability, and configuration remain authoritative. See
[Institutional Knowledge](institutional-knowledge.md).

## Conversation-context boundary

R3 preserves three separate concepts. Session history is the complete sequence of successfully
confirmed turns held in memory by one `ConversationEngine` instance. Selected context is the
continuous suffix sent for one inference after deterministic policies apply. The provider context
window is Ollama's token limit and is neither a character count nor storage.

The default conversation selection budget is 8,000 content characters and ten previous complete
turns. The integrated orchestration policy retains its 10,000-character serialized input budget
after response reserve and additionally accounts for protocol framing, tool schemas, calls, and
results. Both policies preserve the system instruction, current message, complete ordered turns,
and active structured tool data. Removing a turn from selected context never removes it from
confirmed session history.

Long answers consume later context and can cause an entire recent turn plus older turns to be
omitted. Shorter proportional R1 responses improve available capacity but R3 imposes no response
truncation or generation limit. There is no summarization, fact extraction, semantic retrieval,
embedding, RAG, or promise that omitted information remains available to the model. Immutable
context metrics expose counts and sizes without exposing content. See
[Conversation Engine](conversation-engine.md) and [Core Orchestration](core-orchestration.md).

## Effort levels

Effort levels are Kosmos Core abstractions, not native Qwen levels. The installed model exposes
thinking as enabled or disabled; Kosmos coordinates bounded inference count, tool proposals,
deadline, and streaming policy.

- **Instant:** thinking disabled; direct, low-latency answers and simple conversation.
- **Low:** thinking disabled; everyday tool use and simple system queries.
- **Medium:** thinking enabled; reasoning, task planning, and problem analysis.
- **High:** thinking enabled; deeper bounded analysis and multiple explicitly authorized tools.
- **Expert:** reserved for future authorized specialized delegation; unsupported in Stage 01.6.
- **Auto:** reserved for future automatic selection; unsupported in Stage 01.6.

Effort never grants authority. High does not enable external research, delegation, or additional
permissions. Low is the configurable default. See [Effort Levels](effort-levels.md).

## Tool-calling boundary

Stage 01.5 adds provider-independent structured tool requests and responses, an explicit registry,
deterministic schema validation, execution-scoped authorization, sequential execution, and two
pure local tools. The optional `ToolCallingProvider` capability does not change the text-only
`LLMProvider` contract. The Ollama adapter translates structured proposals but has no dependency on
the registry, authorization, or executor and never runs handlers.

Registration does not grant permission. Only explicitly allowed `PURE` tools can execute in this
stage; read-only, state-changing, and sensitive classes remain blocked. Stage 01.6 composes these
contracts into a bounded sequential loop with integrated context budgeting, duplicate call-ID
protection, atomic confirmation, timeout, cancellation, and metrics. It adds no retries, external
tools, cross-turn replay protection, or approval UI. See
[Tool Calling and Tool Registry](tool-calling.md) and
[Core Orchestration](core-orchestration.md).

## Optional external intelligence

Remote intelligence must remain optional, replaceable, explicitly authorized, and transparent:

- Google Gemini API is a planned complement for document analysis, complex information
  processing, and specific delegated tasks.
- Codex is a planned specialized development agent for repository analysis, implementation,
  testing, and technical review.
- Claude Code is a planned specialized engineering agent for architecture review, code analysis,
  and feature development.
- GroqCloud, OpenRouter, and other providers may be evaluated when technically justified.

Kosmos must not assume unlimited free access, permanent model availability, or programmatic rights
based only on an application subscription. It must use authorized provider mechanisms and must not
send local data without appropriate authorization.

## Cost and dependency policy

Kosmos must remain usable without paid APIs, subscriptions, credits, per-request charges, or
silent paid fallbacks. Free, local, and offline technologies are preferred. A free external
service still requires explicit approval, a concrete need, transparent data boundaries, and legal
compatibility; its availability or limits must never be assumed permanent. Hardware, electricity,
and operator-managed infrastructure costs are distinct from service usage fees.

## Planned web intelligence

Future conceptual tools are `web_search`, `web_fetch`, `web_extract`, and `web_research`. SearXNG
is the priority search candidate, subject to technical and licensing review. Trafilatura is a
candidate for content extraction, Beautiful Soup for HTML processing, and Playwright for browser
automation when necessary. None is currently incorporated.

The web layer is planned to retrieve current information, prioritize reliable sources, ground
answers in verifiable evidence, present references, and distinguish facts from inference. Retrieved
content is untrusted and has no authority to approve operations. The design must address prompt
injection, malicious external instructions, and personal-data exposure. Self-hosting a search
frontend does not guarantee local-only processing because queries may still reach external search
engines.
