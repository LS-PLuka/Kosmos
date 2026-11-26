# Development CLI

## Purpose and architecture

Stage 01.7 provides a temporary terminal interface for maintainers to exercise the integrated
Kosmos intelligence path. The CLI is a presentation and composition layer: `CoreOrchestrator`
continues to own conversation coordination, personality, effort policy, context limits, tool
selection, authorization, execution, and controlled results. `OllamaProvider` remains the local
HTTP adapter, and the Conversation Engine remains the sole owner of session history.

The console script is registered as `kosmos = "kosmos.cli.main:main"` and runs with:

```bash
uv run kosmos
```

The synchronous entry point parses arguments and uses `asyncio.run()` for the application
lifecycle. It creates and closes exactly one provider and one in-memory conversation session.

## Prerequisites and configuration

The CLI requires Python 3.12, uv, a running local Ollama service, and an already installed local
model. It never installs, starts, or downloads Ollama or models. Model precedence is:

1. `--model`;
2. `KOSMOS_OLLAMA_MODEL`;
3. the centralized project default, `qwen3.5:4b-q4_K_M`.

The CLI does not select the first installed model and does not fall back to another model. Existing
settings remain supported: `KOSMOS_OLLAMA_BASE_URL`, `KOSMOS_OLLAMA_TIMEOUT_SECONDS`,
`KOSMOS_OLLAMA_MODEL`, `KOSMOS_OLLAMA_CONTEXT_LENGTH`, `KOSMOS_OLLAMA_THINKING`,
`KOSMOS_OLLAMA_KEEP_ALIVE`, and `KOSMOS_LOG_LEVEL`.

The effort policy, rather than `KOSMOS_OLLAMA_THINKING`, determines thinking during orchestrated
conversation turns. The context window is never increased automatically.

## Arguments

```text
--help                 Show help without initializing Ollama.
--version              Show installed package metadata without initializing Ollama.
--effort LEVEL         Use instant, low, medium, or high; low is the default.
--metrics              Display measured operational metrics after each turn.
--no-tools             Use empty tool selection and authorization.
--list-models          List locally installed Ollama models and exit.
--model MODEL          Select one explicit installed model.
```

`expert` and `auto` are reserved and rejected. Argument errors use exit code 2. Expected startup
failures use exit code 1, normal termination uses 0, and top-level Ctrl+C uses 130.

## Internal commands

- `/help` lists local commands.
- `/status` shows session configuration and the startup-verified connection state.
- `/effort [instant|low|medium|high]` shows or changes effort for subsequent turns.
- `/metrics [on|off]` toggles or explicitly controls metrics.
- `/tools` shows registered tool descriptions and current effective authorization.
- `/clear` clears history through `CoreOrchestrator.clear_session()`.
- `/exit` closes the session and provider.

Commands are parsed locally, are never sent to the model, and cannot execute tools directly.
Changing effort or metrics preserves the session, personality, and confirmed history.

## Effort, streaming, and tools

The CLI reads the existing effort policies rather than duplicating their limits. Instant always
uses real textual streaming and has no tools. Low, Medium, and High use complete orchestration when
tools are available. With `--no-tools`, those levels also use real textual streaming because no
structured tool calling is active. Streaming writes fragments progressively, preserves Unicode
and whitespace, closes the iterator in all paths, and commits a turn only after the final provider
event.

The trusted application allowlist contains exactly `calculate` and `count_items`. The CLI never
authorizes tools merely because they appear in a registry. `--no-tools` supplies both empty
selection and empty authorization. Instant policy removes tool availability independently of the
initial allowlist.

## Metrics

Complete orchestration reports software elapsed time, inference counts, tool proposals and
executions, successful and failed or rejected tools, and provider metrics when present. Streaming
reports locally measured elapsed time and final-event provider metrics when present. Provider
durations are converted from nanoseconds to seconds. Tokens per second is calculated only with a
valid generated-token count and a positive generation duration. Missing values are omitted.

## Lifecycle, errors, and terminal security

Startup verifies the Ollama version and installed model list before creating a session. An absent
configured model is reported with a manual `ollama pull` instruction; no command is executed.
Expected provider, timeout, invalid-response, context, inference, tool-limit, and capability
failures are rendered without tracebacks. Recoverable conversation failures return to the prompt.

EOF and `/exit` close normally. Ctrl+C cancels the active operation and exits safely. Active
streams close in `finally`, incomplete turns are not committed, the session is deleted only after
it becomes idle, and the provider context always releases its HTTP client.

User input, model text, tool results, model identifiers, and provider metadata are untrusted for
presentation. The CLI strips ANSI, OSC, and unsafe control characters while preserving legitimate
Unicode, newlines, carriage returns, and tabs. Streaming sanitization buffers incomplete escape
sequences across fragments. Sanitization changes only displayed text, never conversation history.

The loopback restriction prevents accidental remote endpoint configuration, but it cannot inspect
all daemon behavior. On Ubuntu, configure and verify `OLLAMA_NO_CLOUD=1` in the Ollama service
environment and use only local models. Kosmos does not change daemon configuration.

## Ubuntu startup guide

Run these commands later on the maintainer's Ubuntu machine, not as part of automated validation:

```bash
git switch develop
git pull --ff-only origin develop

uv lock --check
uv sync --frozen --dev

ollama list
curl http://127.0.0.1:11434/api/version

uv run kosmos --help
uv run kosmos --list-models
uv run kosmos
```

Verify the Ollama service environment before starting:

```bash
systemctl --user show ollama --property=Environment
```

If Ollama runs as a system service, inspect the applicable system unit instead. Confirm that the
reported environment contains `OLLAMA_NO_CLOUD=1`; the CLI cannot verify this automatically.

Useful validation modes:

```bash
uv run kosmos --effort instant
uv run kosmos --effort low --metrics
uv run kosmos --effort medium --metrics
uv run kosmos --effort high --metrics
uv run kosmos --no-tools
```

## Diagnostics and limitations

- If Ollama is unavailable, verify that the local service is running and that
  `KOSMOS_OLLAMA_BASE_URL` is a valid loopback URL.
- If the model is absent, compare `uv run kosmos --list-models` with the configured identifier and
  install it manually with Ollama.
- For timeouts, inspect the local service and model load, then deliberately adjust
  `KOSMOS_OLLAMA_TIMEOUT_SECONDS` if required. The effort deadline remains independent.
- For a context-limit error, shorten the request or use `/clear`; do not increase context
  automatically.
- For inadequate responses, record the selected model, effort, prompt, and metrics for Stage 01.8
  real behavioral validation. Do not treat automated fake-provider tests as real Qwen evidence.

The CLI has no persistent history, shell execution, file access, voice, GUI, remote fallback,
telemetry, model download, streaming tool calls, or Stage 01.8 benchmark behavior. Real Ubuntu,
Ollama, and Qwen validation remains pending.
