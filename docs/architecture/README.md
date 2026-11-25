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

Modules may later use `domain`, `application`, `infrastructure`, and `presentation` subdirectories,
but only after implemented behavior demonstrates the need. Empty architectural layers are avoided.

## Planned modules

| Module | Planned responsibility |
| --- | --- |
| `core` | General orchestration, lifecycle, and operational coordination |
| `intelligence` | AI models, conversation, reasoning, and tool calling |
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

These directories describe planned boundaries only. Stage 00 does not implement any module.

## Architectural rules

- Prefer high cohesion and low coupling; avoid circular dependencies.
- Keep framework code at boundaries and business rules independently testable.
- Separate intent, authorization, and execution for every sensitive tool action.
- Make external providers replaceable where the product requires choice or offline operation.
- Use synchronous or asynchronous execution according to measured needs, not fashion.
- Record significant cross-cutting decisions as architecture decision records when they arise.
