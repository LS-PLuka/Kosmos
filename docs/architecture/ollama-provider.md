# Ollama Provider

## Implementation status

Stage 01.2 implements the first real Python integration boundary for local text inference. The
adapter and its automated tests are complete, while real inference with Ollama 0.40.18 and
`qwen3.5:4b-q4_K_M` on the target Ubuntu host remains a maintainer validation task. Simulated HTTP
validation must not be presented as model validation.

## Architecture and lifecycle

`OllamaProvider` is an infrastructure adapter inside the `intelligence` module. It translates
provider-independent requests into the documented Ollama API and validated responses back into
immutable Kosmos models. The `LLMProvider` port exposes complete generation and async streaming
without importing HTTPX or Ollama schemas.

Each provider owns one `httpx.AsyncClient`, reuses its connection pool, and closes both the client
and an injected test transport through `aclose()` or `async with`. A closed provider cannot be
reopened. Construction performs no network operation. Consumers that stop streaming early must
call `aclose()` on the async iterator; the response context then releases the connection.

## Configuration

| Environment variable | Default | Validation |
| --- | --- | --- |
| `KOSMOS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | HTTP(S) loopback origin only |
| `KOSMOS_OLLAMA_TIMEOUT_SECONDS` | `120` | finite positive number |
| `KOSMOS_OLLAMA_MODEL` | not configured | non-empty text, reserved for later composition |
| `KOSMOS_OLLAMA_CONTEXT_LENGTH` | `4096` | positive integer |
| `KOSMOS_OLLAMA_THINKING` | `false` | explicit `true` or `false` |
| `KOSMOS_OLLAMA_KEEP_ALIVE` | `5m` | `0` or positive duration in `ms`, `s`, `m`, or `h` |

Settings are immutable and loaded explicitly. Loading them does not change the environment, open a
connection, or select a request model. `KOSMOS_OLLAMA_MODEL` is intentionally not a silent provider
fallback; every `InferenceRequest` still selects its model.

The base URL rejects credentials, non-loopback hosts, paths, queries, fragments, whitespace,
control characters, backslashes, IPv6 scope identifiers, invalid ports, and ambiguous host forms.
`localhost` is normalized to `127.0.0.1` so a modified resolver cannot redirect it. For HTTPS, the
server certificate must therefore be valid for the literal address; certificate verification
remains enabled.

## Complete inference

`generate()` sends `POST /api/chat` with ordered messages, `stream: false`, the effective thinking
flag, keep-alive duration, and `options.num_ctx`. It requires a completed response with an assistant
message and non-empty final content. Optional metrics record API durations in nanoseconds and token
counts as integers. Missing metrics remain absent rather than being invented.

The adapter never includes `message.thinking` in `InferenceResponse.content`. Thinking defaults to
the immutable setting and can be overridden with `InferenceRequest.thinking` without changing that
setting. Effort levels and automatic thinking selection remain outside Stage 01.2.

## Streaming

`stream()` sends the same request with `stream: true` and incrementally reads Ollama NDJSON through
HTTPX. It yields one immutable `InferenceChunk` per valid event, preserving empty text, spaces,
Unicode, order, and final-event content. A `done=true` event is required. Text delivered before that
event is partial output and does not represent a successful completed inference.

Thinking fields are ignored. The final chunk may contain no text and may carry typed metrics. A
malformed event, embedded Ollama error, invalid field, or connection end before `done=true` fails
the stream. The implementation does not concatenate output before yielding it.

## Availability and installed models

`get_version()` validates and returns the string from `GET /api/version`. `list_models()` returns a
tuple of immutable `OllamaModel` values from `GET /api/tags`; an empty tuple is a valid available
service with no installed models. `is_available()` returns `False` only for a connection failure.
Timeouts, HTTP failures, and invalid documents remain distinct exceptions.

The adapter never pulls, updates, deletes, preloads, or automatically selects a model. It performs
no polling or background health checks.

## Errors, timeouts, and cancellation

HTTPX exceptions do not cross the adapter boundary. Connection failures become
`ProviderUnavailableError`, transport inactivity becomes `ProviderTimeoutError`, unsuccessful
statuses become `ProviderHTTPError` with a status code, and malformed schemas become
`InvalidProviderResponseError`. Ollama errors embedded in a successful or streaming response become
`InferenceError`. Error messages and logs omit prompts, response text, thinking, and raw bodies.

The configured HTTPX timeout applies independently to connection, pool acquisition, writes, and
periods waiting for response data. It is not an absolute inference deadline. During streaming, each
new fragment resets the read-inactivity wait. Absolute task limits belong to future Core Engine
orchestration.

`asyncio.CancelledError` is not caught or converted. Cancellation closes the active HTTP response
without retrying or creating background tasks. Closing the connection does not guarantee that an
Ollama server stops internal generation immediately.

## Security and privacy

The client uses `trust_env=False` and `follow_redirects=False`. This disables environment proxies
and environment-provided certificate paths, rejects redirect destinations, and preserves default
TLS verification for HTTPS. Only adapter-defined endpoints are used. There is no remote fallback,
telemetry, credential use, shell execution, or automatic download.

For an exclusively local Ollama runtime, configure the service itself with `OLLAMA_NO_CLOUD=1`.
A loopback API connection alone does not prove that every server-side feature is offline. Kosmos
does not modify the host's Ollama settings.

## Structured tool calling

Stage 01.5 adds the optional provider-independent `ToolCallingProvider` capability to
`OllamaProvider`. `generate_with_tools()` uses the native `/api/chat` `tools` field with
`stream=false` and accepts assistant text, ordered structured calls, or both. It validates protocol
structure, generates local correlation identifiers, and supports explicit continuation through
assistant `tool_calls` messages followed by `role: tool` messages containing `tool_name`.

The adapter does not parse calls from free text and never authorizes or executes a handler. Its
existing text generation and streaming behavior is unchanged. Native streaming tool calls remain
outside this stage. See [Tool Calling and Tool Registry](tool-calling.md) for schemas, limits, and
the manual composition flow.

## Manual Ubuntu demonstration

The following example requires the maintainer's Ubuntu installation, an already installed model,
and Ollama started with cloud functionality disabled. It must not be treated as automated or
Windows validation.

```python
import asyncio

from kosmos.core.config import load_settings
from kosmos.intelligence.models import InferenceRequest, Message, MessageRole
from kosmos.intelligence.providers import OllamaProvider


async def main() -> None:
    settings = load_settings(
        {
            "KOSMOS_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "KOSMOS_OLLAMA_TIMEOUT_SECONDS": "120",
            "KOSMOS_OLLAMA_CONTEXT_LENGTH": "4096",
            "KOSMOS_OLLAMA_THINKING": "false",
            "KOSMOS_OLLAMA_KEEP_ALIVE": "5m",
        }
    )
    request = InferenceRequest(
        model="qwen3.5:4b-q4_K_M",
        messages=(Message(MessageRole.USER, "Hello, Kosmos!"),),
    )

    async with OllamaProvider(settings) as provider:
        response = await provider.generate(request)
        print(response.content)

        iterator = provider.stream(request)
        try:
            async for chunk in iterator:
                print(chunk.content, end="", flush=True)
        finally:
            await iterator.aclose()


asyncio.run(main())
```

Run it later on Ubuntu after setting `OLLAMA_NO_CLOUD=1` in the Ollama service environment and
verifying `ollama list` contains the explicitly selected model. The repository intentionally does
not provide a CLI or alter the real service configuration in this stage.

## Limitations

The adapter does not itself manage conversations or execution. Stage 01.3 adds provider-independent
sessions and confirmed text history above this boundary, while Stage 01.5 adds explicit structured
tool inference without automatic orchestration. Images, embeddings, temperature policy, retries,
effort levels, remote providers, automatic routing, persistent memory, voice, GUI behavior, and
operating-system control remain unavailable.
