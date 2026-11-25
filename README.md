![Kosmos — The intelligence orbiting your world.](assets/branding/banners/kosmos-readme-banner.png)

# Kosmos

**The intelligence orbiting your world.**

![Project status](https://img.shields.io/badge/status-foundation-683A79)
![Python](https://img.shields.io/badge/python-3.12-BE6BB7)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-25192D)

## Overview

Kosmos is a source-available personal AI assistant designed to be local-first, modular,
extensible, and user-controlled. The project is initially targeting Ubuntu and is being built
incrementally as a modular monolith. Local processing is the default design direction; external
providers must be explicit, replaceable integrations rather than hidden requirements.

## Project status

Kosmos is in **Stage 00 — Project Foundation**. The repository currently provides project
structure, engineering standards, Python tooling, continuous integration, and the approved visual
identity package. It does not yet implement an assistant, AI engine, voice pipeline, system
control, persistent memory, automation engine, or desktop application.

Everything described below as planned belongs to the roadmap and must not be interpreted as an
implemented capability.

## Vision

The long-term goal is a proactive desktop assistant inspired by integrated fictional assistants,
while remaining grounded in explicit authorization, transparent execution, privacy, and practical
software engineering. Kosmos should coordinate local intelligence, voice, operating-system tools,
development agents, memory, monitoring, automations, multimodal input, and plugins without making
the graphical interface or any external provider the center of the architecture.

## Planned capabilities

- Local model conversation, reasoning, and tool calling
- Wake word, speech recognition, and speech synthesis
- Operating-system, application, file, process, and Docker interaction
- Development-agent and project workflow integration
- Contextual and persistent memory
- Monitoring, reminders, notifications, and proactive automation
- Explicit permissions and security policies for tool execution
- Control Center, Overlay, and system tray desktop experiences
- External integrations, multimodal processing, and plugins

## Visual identity

The approved Dark Nebula identity uses the Void, Nebula, Cosmic, Nova, and Starlight palette. The
static identity, vector geometry, 12 motion states, reference data, and Motion Lab are preserved in
this repository.

| Institutional symbol | Kosmos Core | Motion example |
| --- | --- | --- |
| ![Institutional symbol](assets/branding/symbols/institutional.png) | ![Kosmos Core](assets/branding/core/core.png) | ![Thinking state](assets/branding/animations/thinking/thinking.gif) |

See the [brand guide](docs/branding/BRAND-GUIDE.md), [motion assets](assets/branding/animations/),
and [Motion Lab](tools/motion-lab/). GIF and WebP files are documentation and approval references;
the future desktop implementation is planned to render approved vector geometry in real time.

## Architecture

Kosmos uses a modular monolith organized by business capability. Domain code should remain
independent of the graphical interface and frameworks. External services and system integrations
will be isolated behind adapters when a real substitution or testing need exists. Internal layer
directories are introduced only as modules acquire behavior, avoiding speculative abstractions.

The planned top-level domains are documented in
[the architecture overview](docs/architecture/README.md).

## Technology stack

Currently configured:

- Python 3.12 with a `src` layout
- uv for environments, dependency resolution, and locking
- Ruff for linting and formatting
- Pytest for automated tests
- GitHub Actions for continuous integration

Planned technologies, subject to evaluation and licensing review, include Ollama, Pydantic,
AsyncIO, SQLite, openWakeWord, Silero VAD, faster-whisper, SoundDevice, Kokoro or Piper, psutil,
Docker SDK, Codex integration, PySide6, and Qt Quick/QML. None is a current runtime dependency.

## Roadmap

1. **Stage 00 — Project Foundation:** repository, tooling, standards, documentation, identity, CI
2. **Stage 01 — Core Engine:** local-model evaluation, Ollama, conversation, providers, tools
3. **Stage 02 — Voice Engine:** wake word, audio, VAD, speech-to-text, text-to-speech
4. **Stage 03 — System Control:** applications, files, processes, resources, Docker, OS integration
5. **Stage 04 — Developer Agent:** Codex, projects, sessions, tasks, execution tracking
6. **Stage 05 — Memory Engine:** context, preferences, persistence, retrieval
7. **Stage 06 — Proactive Engine:** events, monitoring, automations, reminders, notifications
8. **Stage 07 — Desktop Experience:** PySide6, QML, Control Center, Overlay, tray, vector motion
9. **Stage 08 — Extended Integrations:** AWS, Spotify, browser, productivity tools, services
10. **Stage 09 — Multimodal Engine:** webcam, computer vision, image and screen interpretation
11. **Stage 10 — Cross-platform & Ecosystem:** Windows, plugins, distribution, contributors

## Getting started

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uv python install 3.12
uv sync --frozen --dev
uv run python -c "import kosmos; print(kosmos.__version__)"
```

No application entry point exists in Stage 00.

## Development

```bash
uv sync --frozen --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ruff uses a 100-character line limit: wide enough for readable modern Python while still supporting
side-by-side review. See [the development guide](docs/development/README.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

To inspect the visual prototype without dependencies, open `tools/motion-lab/index.html` in a
modern browser. A local HTTP server may be used for optional microphone access as documented in
[the preserved package README](docs/branding/PACKAGE-README.pt-BR.md).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a change. The contribution and future CLA
strategy is documented as a proposal pending maintainer and legal approval.

## License

Kosmos is source-available under the
[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not authorized by the standard
license except where its terms provide otherwise. A separate commercial license may be offered in
the future; none is granted here. Software licensing does not grant rights to use Kosmos names,
logos, or visual identity as trademarks.

## Acknowledgments

The repository uses uv, Ruff, Pytest, Hatchling, GitHub Actions, and the Contributor Covenant as
development or community infrastructure. Applicable notices are recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
