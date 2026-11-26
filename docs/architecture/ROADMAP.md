# Official Roadmap

Kosmos is delivered incrementally. Only validated, merged behavior is implemented; every other
item below is planned or a candidate and requires approval before work begins.

## Stage 00 — Project Foundation

Complete.

## Stage 01 — Core Engine

- **01.1 — Core Foundation:** complete
- **01.2 — Ollama Provider:** adapter implemented and automatically tested; real inference
  validation on the target Ubuntu host remains pending
- **01.3 — Conversation Engine:** complete and integrated into `develop`
- **01.4 — Personality Engine:** implemented and automatically tested on its feature branch;
  maintainer review, integration, and real behavioral validation remain pending
- **01.5 — Tool Calling & Tool Registry:** planned
- **01.6 — Core Orchestration & Effort Levels:** planned
- **01.7 — Development CLI:** planned
- **01.8 — Model Benchmark & Validation:** planned

## Stage 02 — Voice Engine

Planned voice activation, capture, recognition, and synthesis. Candidate technologies are
openWakeWord, SoundDevice, Silero VAD, faster-whisper, Kokoro, and Piper. The Razo Brazilian
Portuguese voice with Piper is the provisional priority for synthesis, subject to technical,
provenance, rights, distribution, and license compatibility review. No voice runtime or model is
incorporated by Stage 01.4.

## Stage 03 — System Control

Planned authorized control of the operating system, applications, files, processes, and resources.

## Stage 04 — Developer Agents

Planned specialized integrations with Codex and Claude Code.

## Stage 05 — Memory Engine

Planned context persistence, retrieval, and memory.

## Stage 06 — Proactive Intelligence

Planned monitoring, events, routines, and proactive automations.

## Stage 07 — Desktop Experience

Planned PySide6, Qt Quick, and QML Control Center, Overlay, system tray, and approved visual
identity. All candidate technologies require their applicable technical and licensing review.

## Stage 08 — Web Intelligence & External Integrations

Planned internet research, grounded answers, Google Gemini API, and other optional external
integrations.

## Stage 09 — Multimodal Intelligence

Planned image processing, computer vision, and multimodal interaction.

## Stage 10 — Cross-platform & Ecosystem

Planned expansion of runtime compatibility, extensibility, and ecosystem support.
