# Core Foundation

Stage 01.1 establishes the minimum provider-independent foundation needed for later local-model
integration. It does not make Kosmos an operational assistant and does not connect to Ollama or any
other external service.

## Core responsibilities

The `core` module currently provides:

- immutable, explicitly loaded application settings;
- validation errors shared by configuration and inference boundaries;
- explicit configuration of the `kosmos` logger without changing the root logger.

Importing the package does not read environment variables or configure logging. Callers choose
when to call `load_settings` and `configure_logging`, which keeps startup behavior visible and tests
deterministic.

## Configuration

| Environment variable | Default | Validation |
| --- | --- | --- |
| `KOSMOS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `KOSMOS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | HTTP(S), no credentials, loopback host only |
| `KOSMOS_OLLAMA_TIMEOUT_SECONDS` | `120` | finite number greater than zero |
| `KOSMOS_OLLAMA_MODEL` | not configured | non-empty text when explicitly set |

The model is never selected automatically. Loading settings performs no network operation and does
not mutate the process environment. The timeout is preliminary configuration: its effective
connection and request semantics will be defined when the HTTP adapter is implemented.

## Intelligence responsibilities

The `intelligence` module currently owns provider-independent concepts for complete text inference:

- `MessageRole` with `system`, `user`, and `assistant` values;
- immutable `Message`, `InferenceRequest`, and `InferenceResponse` dataclasses;
- the asynchronous `LLMProvider.generate` protocol.

Requests require a caller-selected model and at least one valid message. Message order is retained,
and input sequences are copied into tuples to prevent later caller mutation. The contract has no
dependency on Ollama, HTTP libraries, graphical interfaces, or persistence.

## Logging and privacy

`configure_logging` adds one marked console handler to the `kosmos` logger and reuses it on repeated
configuration. It includes a timestamp, logger name, level, and message. It does not call
`logging.basicConfig`, replace external handlers, or change the root logger. Application code must
not log prompts, model responses, credentials, or personal information by default.

## Test strategy

Unit tests cover validation, immutability, ordering, explicit logging behavior, and the provider
port. A fake provider lives only under `tests/fakes`; it records requests and returns a configured
response or raises a configured error. Tests require no network, Ollama process, model, or GPU.

## Current limitations and next substage

Stage 01.1 supports only complete textual generation at the contract level. It intentionally has no
Ollama adapter, HTTP client, streaming, model availability checks, generation parameters, metrics,
embeddings, images, tool calls, conversation engine, persistence, CLI, or graphical interface.

The next substage may implement the Ollama HTTP adapter and define concrete timeout and response
handling behavior, but that work is outside Stage 01.1 and requires separate approval.
