# Development CLI

## Purpose and architecture

R5 refines the temporary terminal interface used by maintainers to exercise the integrated Kosmos
intelligence path. The CLI remains a presentation and composition layer: `CoreOrchestrator`
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
`KOSMOS_OLLAMA_KEEP_ALIVE`, `KOSMOS_CONVERSATION_MAX_HISTORY_TURNS`,
`KOSMOS_CONVERSATION_MAX_CONTEXT_CHARACTERS`, and `KOSMOS_LOG_LEVEL`.

The effort policy, rather than `KOSMOS_OLLAMA_THINKING`, determines thinking during orchestrated
conversation turns. The context window is never increased automatically. The CLI constructs its
`ContextPolicy` from the validated conversation settings. The defaults are 10 previous complete
turns and 8,000 content characters; the integrated orchestration budget remains 12,000 serialized
characters with a 2,000-character response reserve.

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
- `/status` shows the Kosmos version, startup-verified provider version and loopback connection,
  selected model, session identifier, effective effort, thinking, tools, metrics state, and the
  configured provider, conversation, orchestration, integrated-input, and response-reserve limits.
- `/effort [instant|low|medium|high]` shows or changes effort for subsequent turns.
- `/metrics [on|off]` toggles or explicitly controls metrics.
- `/tools` distinguishes tools effectively available for the current turn from tools that are only
  registered and disabled. Registration alone never implies authorization.
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
event. If the stream ends, fails, times out, or is cancelled after text has been displayed but
before the required completion event, the CLI prints a separate interruption notice. The partial
text is not added to confirmed history and completion metrics are not shown.

The trusted application allowlist contains exactly `calculate` and `count_items`. The CLI never
authorizes tools merely because they appear in a registry. `--no-tools` supplies both empty
selection and empty authorization. Instant policy removes tool availability independently of the
initial allowlist.

## Metrics

Complete orchestration reports software elapsed time, started and completed inference counts, tool
proposals, handlers invoked, successful and failed or rejected tools, and provider metrics when
present. Multiple inference blocks are numbered and never combined as if they were one provider
window. Streaming reports locally measured elapsed time and final-event provider metrics when
present.

With metrics enabled, both paths render the content-free R3 context measurements produced by the
Core Engine. Conversation selection separates omissions caused by the turn limit and conversation
character budget. Every provider request then reports its request kind, selected message
characters, compact serialized characters against the integrated input budget, response reserve,
and any additional complete turns removed by integrated fitting. These omission counts describe
different selection stages and are not added together as one total. Tool orchestration labels each
request independently.
The configured provider context window is shown in tokens alongside these character measurements;
it is configuration evidence, not an independently measured capacity.

Streaming also measures `Time to first visible text` with `time.monotonic()`, from immediately
before the first stream event is requested until the first sanitized, non-whitespace text is
written. The fixed `Kosmos:` prefix, empty chunks, discarded control sequences, and hidden thinking
do not count. No value is emitted when visible text never arrives. This is presentation latency,
not model-internal token TTFT, and it is not fabricated for complete or tool-calling generation.

Provider durations are converted from nanoseconds to seconds. Tokens per second is calculated only
with a valid generated-token count and a positive provider generation duration. The provider's
generated-token count may include hidden thinking; it is not described as visible-only output.
Missing values are omitted.

Tool evidence correlates structured proposals and results without displaying arguments. A proposal
that was never executed is shown as `proposed`; successful, rejected, and failed outcomes use the
actual `ToolResult` status. Successful built-in pure tools may show their compact numeric result.
Evidence from an already executed tool remains visible if the final response fails.

## Lifecycle, errors, and terminal security

Startup verifies the Ollama version and installed model list before creating a session. An absent
configured model is reported with a manual `ollama pull` instruction; no command is executed.
Expected provider unavailability, provider timeout, provider HTTP failure, invalid response,
inference failure, context, inference-limit, tool-limit, orchestration timeout, and capability
failures are rendered without tracebacks. Recoverable conversation failures return to the prompt.

EOF and `/exit` close normally. Ctrl+C cancels the active operation and exits safely. Active
streams close in `finally`, incomplete turns are not committed, the session is deleted only after
it becomes idle, and the provider context always releases its HTTP client.

User input, model text, tool results, model identifiers, and provider metadata are untrusted for
presentation. The CLI strips ANSI, OSC, C1 control sequences, carriage returns, and unsafe control
characters while preserving legitimate Unicode, newlines, and tabs. Streaming sanitization buffers
incomplete escape sequences across fragments. Sanitization changes only displayed text, never
conversation history or structured results.

The loopback restriction prevents accidental remote endpoint configuration, but it cannot inspect
all daemon behavior. On Ubuntu, configure and verify `OLLAMA_NO_CLOUD=1` in the Ollama service
environment and use only local models. Kosmos does not change daemon configuration. Accordingly,
`Connection: Local loopback (verified at startup)` is a narrow connection statement, not proof of
offline operation, disabled cloud features, complete privacy, or zero external network activity.

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
- For inadequate responses, record the selected model, effort, prompt, and metrics for deferred
  real behavioral validation. Do not treat automated fake-provider tests as real Qwen evidence.

The CLI has no persistent history, shell execution, file access, voice, GUI, remote fallback,
telemetry, model download, or streaming tool calls. Real Ubuntu, Ollama, Qwen, and offline
validation remains pending after the automated R6 audit.
