# AI Agent Engineering Guide

## Authority and scope

This file is the primary engineering instruction source for AI agents working on Kosmos. Read the
existing code and relevant documentation before editing. Follow explicit user instructions first,
then this guide. Do not advance to another roadmap stage unless the user explicitly requests it.

## Project context

Kosmos is a source-available, local-first personal AI assistant. Stage 00 is complete and Stage 01
is in development. Only the Core Foundation behavior documented for Stage 01.1 is currently
implemented; do not claim that later roadmap capabilities are available.

## Engineering principles

- Prefer simple, cohesive, testable code and incremental delivery.
- Apply SOLID, Clean Architecture, ports and adapters, and DDD only where they solve a concrete
  problem. KISS and YAGNI take precedence over speculative structure.
- Use composition over inheritance when it improves clarity.
- Do not create empty interfaces, factories, services, repositories, or layers.
- Keep business logic independent from frameworks and graphical presentation.
- Isolate external providers and operating-system integrations when substitution, security, or
  testing requires a boundary.
- Prevent circular dependencies and preserve a consistent dependency direction.
- Keep Kosmos a modular monolith; do not introduce microservices without an approved architectural
  change.

## Domain boundaries

- `core`: lifecycle, orchestration, and operational coordination
- `intelligence`: AI providers, conversation, reasoning, and tool calling
- `voice`: activation, capture, recognition, and synthesis
- `system`: operating system, applications, files, and processes
- `developer`: development agents, projects, sessions, and tasks
- `memory`: context, persistent memory, and retrieval
- `monitoring`: infrastructure, service, and resource monitoring
- `automation`: scheduling, events, routines, and proactive behavior
- `integrations`: external service integrations
- `security`: authorization, permissions, and execution policy
- `desktop`: Control Center, Overlay, tray, and visual engine
- `vision`: computer vision and multimodal processing
- `plugins`: extension mechanisms

Create internal `domain`, `application`, `infrastructure`, or `presentation` directories only when
implemented behavior requires them.

## Language and naming

Use English for code, identifiers, file and directory names, comments, docstrings, developer-facing
messages, tests, technical documentation, branches, issues, pull requests, and commits. Follow
Python naming conventions. Existing approved branding documents in Portuguese are immutable
historical artifacts and are the only current exception. Design future user-facing interfaces for
internationalization.

## Python and quality

- Target Python 3.12 and use the `src` layout.
- Manage dependencies and environments with uv; do not hand-edit `uv.lock`.
- Format and lint with Ruff using the configured 100-character line limit.
- Write focused Pytest tests for real behavior and regressions. Avoid tests that merely restate an
  implementation.
- Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` for relevant
  changes. Report any check that could not be run.
- Keep documentation synchronized with behavior. Never describe planned behavior as available.

## Dependencies and licensing

Add dependencies only for a concrete, current requirement. Verify the direct license and relevant
transitive or model terms before adding one, record incorporated components in
`THIRD_PARTY_NOTICES.md`, and regenerate the lockfile. Do not install AI models, Ollama, or planned
runtime technologies without explicit authorization. Give PySide6/Qt, AI and speech models, fonts,
graphics, and proprietary services an explicit licensing review.

Kosmos is licensed under `PolyForm-Noncommercial-1.0.0` and must be described as source-available,
not OSI open source. Do not replace or modify the license. Software licensing, asset copyright, and
trademark policy are distinct. Do not assert trademark registration or invent ownership.

## Security and privacy

- Default to least privilege and local processing.
- Separate user intent, authorization, and execution.
- Require explicit authorization for sensitive actions and allow cancellation.
- Validate untrusted input and isolate integrations.
- Never add secrets, credentials, private data, recordings, or local databases to the repository.
- Never transmit data silently to an external provider.
- Keep logs free of unnecessary sensitive data and make executed actions transparent.
- Never execute destructive commands automatically or weaken security controls for convenience.

## Approved visual identity

Treat `assets/branding`, `tools/motion-lab`, `docs/branding`, and `approved-manifest.json` as approved
artifacts. Preserve geometry, animation behavior, source code, specifications, and relative paths.
Do not regenerate, recolor, optimize, or rewrite these files without explicit scope and integrity
validation. Verify affected assets against SHA-256 values before and after moves. GIF and WebP files
are references; they are not the planned production renderer.

## Git workflow

Use GitFlow with permanent `main` and `develop` branches and short-lived `feature/*`, `fix/*`,
`hotfix/*`, `release/*`, `docs/*`, `refactor/*`, or `chore/*` branches. Integrate through pull
requests using merge commits exclusively; squash merges and rebase merges are prohibited. Required
CI checks must pass before integration. Never delete `main` or `develop`; delete eligible temporary
branches after their pull requests are merged. Do not force-push permanent branches, rewrite
published history, create releases or tags without delivered versions, or commit/push unless
explicitly authorized.

Use Semantic Versioning and English Conventional Commits, for example:

```text
feat(intelligence): add local model provider
fix(voice): handle audio stream interruption
docs: clarify development setup
```

## Change discipline

- Keep changes within the requested scope and preserve unrelated user work.
- Inspect existing code and repository status before modifying files.
- Do not install tools, modify remotes, or perform destructive actions without authorization.
- Validate completion with real checks; do not simulate results or hide limitations.
- Update relevant docs and explain significant decisions, tradeoffs, and pending approvals.
- Do not expose sensitive information in commands, output, logs, fixtures, or examples.
