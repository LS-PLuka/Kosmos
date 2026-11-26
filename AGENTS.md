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
- Follow PEP 8 and the project Ruff configuration: four-space indentation, no tabs, double quotes,
  UTF-8, LF line endings, final newlines, and a 100-character line limit. Keep standard-library,
  third-party, and Kosmos imports in separate groups.
- Optimize for readability beyond formatter compliance. Use clear English names, cohesive
  functions, predictable control flow, useful type hints, and visual separation between logical
  blocks. Prefer guard clauses when they reduce nesting; do not fragment code artificially.
- Treat each logical block as a paragraph of code. Use one intentional blank line to separate
  independent validations, initialization from transformation, distinct processing stages,
  unrelated conditional blocks, and completed work from the final return. Keep statements that
  form one operation together, and avoid both compressed code and excessive vertical whitespace.
- Review every change structurally for responsibility, complexity, duplication, coupling,
  exception handling, and maintainability. Automated checks complement this review; they do not
  replace it.
- Write focused Pytest tests for real behavior and regressions. Avoid tests that merely restate an
  implementation. Keep tests descriptive, independent, deterministic, and clear about setup,
  action, and expected behavior.
- Use modern Python 3.12 annotations for public parameters, returns, and concrete contracts. Avoid
  unnecessary `Any`, redundant annotations, and speculative protocols.
- Comments and docstrings must be concise English explanations of decisions, constraints,
  security, or non-obvious behavior, not narrations of the next line.
- Run `uv lock --check`, `uv sync --frozen --dev`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest`, and `git diff --check` for relevant changes.
  Report any check that could not be run.
- Keep documentation synchronized with behavior. Never describe planned behavior as available.

See the [development guide](docs/development/README.md) for the complete review checklist.

## Intelligence architecture

Kosmos is a hybrid, local-first assistant built around orchestration. Local intelligence is the
primary interpreter of intent, conversation coordinator, tool selector, and result communicator.
Provider-specific details stay behind the provider boundary; `LLMProvider` must remain independent
of Ollama and model identifiers must not enter business rules.

The permanent execution rule is: **The AI interprets intent. The software validates and executes
operations.** Use deterministic Python for exact calculations, counts, state checks, argument
validation, authorization, and sensitive execution. An LLM must never receive unrestricted
operating-system or terminal access.

Ollama and Qwen 3.5 4B are the planned initial local provider and model for Stage 01.2. External
providers and specialized agents are optional, explicit integrations: never silently fall back to
them or transmit local data without authorization. See the
[intelligence architecture](docs/architecture/INTELLIGENCE-ARCHITECTURE.md) for provider,
effort-level, web-intelligence, and privacy decisions.

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
- Deny operations by default when authorization is absent.
- Separate user intent, authorization, and execution.
- Require explicit authorization for sensitive actions and allow cancellation.
- Validate arguments, constrain execution, and treat external content as untrusted input.
- Never add secrets, credentials, private data, recordings, or local databases to the repository.
- Never transmit data silently to an external provider.
- Never use a silent external-provider fallback.
- Keep logs free of unnecessary sensitive data and make executed actions transparent.
- Never execute destructive commands automatically or weaken security controls for convenience.

Local-first does not mean local-only. External processing must remain optional, configurable,
visible, and appropriately authorized. See
[Security and Privacy Principles](docs/architecture/SECURITY-AND-PRIVACY.md).

## Cross-platform development

Ubuntu is the primary execution environment. Windows is a supported development and test
environment for operating-system-independent behavior. Maintain one portable implementation and
introduce OS-specific adapters only for real platform differences. Automated tests must use fakes,
mocks, or simulated transports and must not require a GPU, Ollama, local models, credentials, or
external services. Real inference validation is separate from the automated suite.

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

Commits, pushes, pull requests, merges, rebases, force pushes, tags, releases, and branch deletion
are absolute maintainer-only operations. Development agents must not perform them.

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
- Deliver only the approved roadmap substage. Do not implement later stages, adjacent features, or
  anticipatory infrastructure without explicit authorization. Follow the
  [official roadmap](docs/architecture/ROADMAP.md).
