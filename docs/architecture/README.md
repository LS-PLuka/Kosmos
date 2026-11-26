# Architecture Overview

Kosmos starts as a modular monolith organized by business capability. This choice keeps deployment,
local operation, refactoring, and cross-module transactions simple while preserving explicit
boundaries. It is not a temporary microservice decomposition.

## Dependency direction

Business behavior must not depend directly on graphical frameworks or external providers. The
desktop layer presents state and user intent; it does not execute tools or decide authorization.
The Core Engine must remain usable without a GUI. System and service integrations should be kept at
the edge and introduced behind adapters when a concrete testing, replacement, or security need
exists.

Kosmos is a hybrid, local-first orchestration system. The local model interprets intent and
coordinates conversation, but software owns validation, authorization, deterministic operations,
and execution. External intelligence is optional and must never become a hidden runtime
requirement. The detailed decisions are in the
[Intelligence Architecture](INTELLIGENCE-ARCHITECTURE.md).

Modules may later use `domain`, `application`, `infrastructure`, and `presentation` subdirectories,
but only after implemented behavior demonstrates the need. Empty architectural layers are avoided.

## Module status

| Module | Responsibility and current status |
| --- | --- |
| `core` | Application foundations are implemented; orchestration and lifecycle remain planned |
| `intelligence` | Text inference models, streaming port, Ollama adapter, and in-memory Conversation Engine are implemented; Stage 01.3 integration and real Ubuntu inference validation remain pending, while reasoning and tool calling are planned |
| `voice` | Activation, capture, recognition, and speech synthesis |
| `system` | Operating system, applications, files, and processes |
| `developer` | Development agents, projects, sessions, and tasks |
| `memory` | Context, persistent memory, and information retrieval |
| `monitoring` | Infrastructure, service, and resource monitoring |
| `automation` | Scheduling, events, routines, and proactive actions |
| `integrations` | External service integrations |
| `security` | Authorization, permissions, and execution policies |
| `desktop` | Control Center, Overlay, tray, and visual engine |
| `vision` | Computer vision and multimodal processing |
| `plugins` | Kosmos extension mechanisms |

Directories other than `core` and `intelligence` still describe planned boundaries only. See the
[Core Foundation specification](core-foundation.md) for the behavior currently available.

## Architectural rules

- Prefer high cohesion and low coupling; avoid circular dependencies.
- Keep framework code at boundaries and business rules independently testable.
- Separate intent, authorization, and execution for every sensitive tool action.
- Make external providers replaceable where the product requires choice or offline operation.
- Use synchronous or asynchronous execution according to measured needs, not fashion.
- Record significant cross-cutting decisions as architecture decision records when they arise.
- Prefer deterministic software over LLM output for exact calculations, counts, state checks,
  validation, authorization, and execution.
- Deny unauthorized operations by default and prohibit unrestricted terminal access by an LLM.

## Implemented dependency boundary

The `intelligence` models represent Kosmos concepts and do not expose an Ollama or HTTP schema.
Application code depends on the asynchronous `LLMProvider` protocol for complete and streaming
inference. `OllamaProvider` is an edge adapter that depends inward on this port and the models.
Tests and future integrations can substitute implementations without changing the domain boundary.

## Architectural references

- [Core Foundation](core-foundation.md): implemented Stage 01.1 behavior
- [Ollama Provider](ollama-provider.md): implemented Stage 01.2 adapter and pending real validation
- [Conversation Engine](conversation-engine.md): implemented Stage 01.3 in-memory conversation
  management pending maintainer integration
- [Intelligence Architecture](INTELLIGENCE-ARCHITECTURE.md): planned hybrid intelligence,
  providers, effort levels, and web research
- [Security and Privacy Principles](SECURITY-AND-PRIVACY.md): trust and authorization constraints
- [Official Roadmap](ROADMAP.md): incremental delivery stages and implementation status
