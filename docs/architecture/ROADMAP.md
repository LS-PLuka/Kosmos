# Official Roadmap

Kosmos is delivered incrementally. Integrated behavior, refinement-branch implementation, and
pending validation are identified separately below. Every other item is planned or a candidate and
requires approval before work begins.

## Stage 00 — Project Foundation

Complete.

## Stage 01 — Core Engine

- **01.1 — Core Foundation:** complete
- **01.2 — Ollama Provider:** adapter implemented and automatically tested; real inference
  validation on the target Ubuntu host remains pending
- **01.3 — Conversation Engine:** complete and integrated into `develop`
- **01.4 — Personality Engine:** complete and integrated into `develop`; real behavioral
  validation remains pending
- **01.5 — Tool Calling & Tool Registry:** complete and integrated into `develop`; real Qwen
  validation remains pending
- **01.6 — Core Orchestration & Effort Levels:** complete and integrated; real Qwen validation
  remains pending
- **01.7 — Development CLI:** complete and integrated; real Ubuntu and Qwen validation remain
  pending
- **01.8 — Model Benchmark & Validation:** benchmark infrastructure implemented and automatically
  tested; real model and offline validation on the target Ubuntu host remain pending

Core runtime refinement status:

- **R1 — Personality & Communication:** implemented on the current refinement branch
- **R2 — Institutional Knowledge:** implemented on the current refinement branch
- **R3 — Conversation & Context:** implemented on the current refinement branch
- **R4 — Tool Calling & Reasoning:** implemented on the current refinement branch
- **R5 — Runtime & CLI Refinement:** implemented on the current refinement branch
- **R6 — Regression & Final Validation:** automated regression review passed on the current
  refinement branch; maintainer review and integration remain pending

Stage 01 implementation is complete on the refinement branch. Live runtime, Qwen behavioral,
performance, hardware, and offline validation remain pending and must not be inferred from the
automated suite.

## Stage 02 — Voice Engine

- **02.1 — Voice Foundation:** implemented on `feature/voice-foundation` with automated validation;
  physical Windows and Ubuntu audio validation and Git integration remain pending
- **02.2 — Text-to-Speech:** planned
- **02.3 — Speech-to-Text:** planned
- **02.4 — Voice Activity Detection:** planned
- **02.5 — Wake Word Detection:** planned
- **02.6 — Voice Orchestration:** planned
- **02.7 — Real-Time Voice Interaction:** planned
- **02.8 — Voice Benchmark & Validation:** planned

Stage 02.1 provides backend-independent PCM models and ports, bounded capture and playback,
SoundDevice/PortAudio discovery, optional installation, and explicit diagnostics. It does not
implement speech synthesis, recognition, VAD, wake words, orchestration, or real-time interaction.
SoundDevice is incorporated only in the optional `voice` extra. Piper, the provisional Razo voice,
faster-whisper, Silero VAD, and openWakeWord remain candidates subject to their stage-specific
technical, provenance, rights, distribution, and license reviews.

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
