# Conversation Engine

## Implementation status

Stage 01.3 implements provider-independent, in-memory conversation management. R3 refines its
context budget, configuration, and privacy-safe selection metrics. Real Ollama inference on Ubuntu
remains pending and is not validated by the deterministic test suite.

## Objective and responsibilities

The Conversation Engine turns individual provider calls into isolated conversation sessions. It
owns session identity, confirmed message history, context selection, turn integrity, and
cooperative asynchronous concurrency per session. It delegates text generation to the injected
`LLMProvider` and does not know about Ollama, HTTPX, model installations, GPUs, or endpoints.

The engine does not define a personality, execute tools, persist memory, select a model implicitly,
or own the provider lifecycle. Stage 01.4 supplies personality through the existing explicit
system-instruction boundary. The caller must select a model for every turn and close any provider
it created.

```text
Caller
  -> ConversationEngine
       -> in-memory session
       -> ContextPolicy
       -> LLMProvider
```

## Public contracts

The `kosmos.intelligence.conversation` package exports:

- `ConversationEngine(provider, context_policy=None)`
- `ContextPolicy(max_history_turns=10, max_context_characters=8000)`
- `ContextSelection` and immutable `ContextSelectionMetrics`
- `ConversationSession`
- `ConversationStream`

`ConversationEngine` provides `create_session()`, `get_session()`, `list_sessions()`,
`clear_session()`, `delete_session()`, `generate()`, `run_turn()`, and `stream()`. Session identifiers are
standard-library `UUID` values. Returned sessions are immutable snapshots whose message history is
a tuple, so callers cannot mutate managed state by retaining a reference.

## Sessions and message history

Sessions exist only in the engine instance that created them. Each session stores an optional
system instruction separately from its confirmed turn history. The public `messages` tuple contains
only chronologically ordered `USER` and `ASSISTANT` pairs. A turn is appended only after a valid
provider completion.

Clearing removes confirmed turns while preserving the UUID and system instruction. Deleting removes
the managed reference. These operations are logical removal, not guaranteed physical erasure from
process memory. Unknown identifiers raise `SessionNotFoundError`; the engine never creates a
replacement session for an invalid identifier.

## Context selection

`ContextPolicy` builds each request in this order:

1. the explicit system instruction, when present;
2. a continuous suffix of complete prior `USER`/`ASSISTANT` turns;
3. the current user message.

It first limits prior turns, then walks backward from the newest eligible turn while complete pairs
fit the character budget. Selected messages are restored to chronological order. If the newest
candidate does not fit, older turns are not selected because that would break suffix continuity.
The policy never truncates a message or changes the stored history.

The system instruction and current user message are mandatory. If their combined text exceeds
`max_context_characters`, `ContextLimitExceededError` is raised before the provider is called. A
zero `max_history_turns` intentionally disables prior-turn context; negative values are invalid.

Character count is a deterministic preliminary heuristic over message content. It does not count
protocol framing and is not a token count. In particular, it cannot guarantee compliance with
Ollama's separately configured model context length. Tokenization, summarization, semantic
compression, RAG, embeddings, and LLM-based selection remain outside this stage.

R3 raises only the default content budget from 6,000 to 8,000 characters. The ten-turn limit is
unchanged. `KOSMOS_CONVERSATION_MAX_HISTORY_TURNS` accepts zero to disable prior history, and
`KOSMOS_CONVERSATION_MAX_CONTEXT_CHARACTERS` requires a positive integer. `ApplicationSettings`
validates both values and the CLI and benchmark pass them explicitly into `ContextPolicy`.

`select_with_metrics()` returns the same messages as `select()` plus counts for total confirmed,
eligible, selected, turn-limit omitted, character-limit omitted, aggregate omitted turns, selected
content characters, and the applied content budget. The metrics contain no message text. Aggregate
omissions equal total confirmed minus selected, so a turn excluded by the turn limit is not counted
again as a character omission.

## Deterministic R3 reproduction

An automated fake-message regression uses eight 600-character confirmed turns, a 2,500-character
system instruction, and a 100-character current message. The former 6,000-character policy selects
the newest five turns, uses 5,600 content characters, and omits the oldest three turns. The R3
8,000-character policy selects all eight and uses 7,400 characters. This proves which messages the
software includes; it does not prove semantic recall by Qwen or exclude provider truncation.

A long recent assistant response can still prevent its complete turn and every older turn from
fitting. The full response remains in session history, but suffix continuity prevents skipping that
turn to recover older facts. R3 deliberately does not truncate, summarize, pin, semantically rank,
or persist messages.

## Complete inference

`generate()` validates the session, user text, explicit model, optional thinking flag, and session
availability before constructing an immutable `InferenceRequest`. It calls `provider.generate()`
once. A valid `InferenceResponse` is returned unchanged, preserving provider model, content, and
metrics. The engine stores only the user content and final assistant content.

Provider errors, timeouts, invalid responses, and `asyncio.CancelledError` propagate without being
converted into conversation messages. The prior history remains unchanged and the session is made
available in a `finally` path.

## Streaming and iterator lifecycle

`stream()` reserves the session synchronously and calls `provider.stream()` exactly once. The
returned `ConversationStream` yields non-final chunks immediately, preserving their order, content,
Unicode, spaces, model, completion flag, and metrics. It concatenates only textual content needed
for the final assistant message.

The final `done=True` chunk is held until the accumulated response is validated, the upstream
iterator is closed, and the complete turn is committed. Final-event content participates in the
assistant message. A missing final event or a final result containing only whitespace raises
`InvalidProviderResponseError` and does not alter history.

If a consumer stops before completion, it may already have displayed partial text that is not part
of confirmed history. The consumer must call `await stream.aclose()` in a `finally` block (or use
`contextlib.aclosing`) to close the provider iterator and release the session. Calling `stream()`
and never consuming or closing the returned iterator intentionally leaves the session reserved;
the engine creates no background task that could infer abandonment.

Cancellation and provider failures close the upstream iterator, discard accumulated partial text,
release the session, and propagate the original failure. The engine never closes the injected
provider itself.

## Concurrency and lifecycle

The busy flag is set before the provider can suspend. A second turn, clear, or delete operation on
that session raises `SessionBusyError`. Different sessions can progress independently in one
cooperative event loop. There are no queues, workers, executors, or orphaned tasks.

This design does not promise thread safety, multi-process coordination, durable retention, or
distributed scalability. Engine instances and their sessions should be used within one event loop.

## Errors

Conversation-specific errors extend the existing `KosmosError` hierarchy:

- `ConversationError`
- `SessionNotFoundError`
- `SessionBusyError`
- `ContextLimitExceededError`

Provider-specific exceptions remain unchanged. Error messages contain no conversation text.

## Security and privacy

Conversation state is retained only in process memory. The engine performs no file or database
writes, logging of message content, telemetry, external fallback, tool invocation, command
execution, or authorization inference. Data is sent only to the explicitly injected provider as
part of the requested inference. Isolation between sessions is enforced by separate managed
histories.

In-memory storage is not a complete retention or security mechanism. Python objects may remain in
physical memory after references are removed, and the engine does not provide secure erasure.

## Example

This network-free example uses the repository fake provider and the actual public API:

```python
import asyncio

from kosmos.intelligence.conversation import ConversationEngine
from kosmos.intelligence.models import InferenceChunk, InferenceResponse
from tests.fakes.llm_provider import FakeLLMProvider


async def main() -> None:
    provider = FakeLLMProvider(
        response=InferenceResponse(model="test-model", content="Understood.")
    )
    engine = ConversationEngine(provider)
    session = engine.create_session(system_instruction="Answer clearly.")

    await engine.generate(
        session.session_id,
        "My project uses Java 21 and Spring Boot.",
        model="test-model",
    )

    provider.response = InferenceResponse(
        model="test-model",
        content="PostgreSQL is a strong general-purpose choice.",
    )
    await engine.generate(
        session.session_id,
        "Which database would you recommend?",
        model="test-model",
    )

    provider.response = None
    provider.chunks = (
        InferenceChunk(model="test-model", content="It "),
        InferenceChunk(model="test-model", content="depends.", done=True),
    )
    stream = engine.stream(
        session.session_id,
        "Can you qualify that recommendation?",
        model="test-model",
    )
    try:
        async for chunk in stream:
            print(chunk.content, end="")
    finally:
        await stream.aclose()

    print(engine.get_session(session.session_id).messages)
    engine.clear_session(session.session_id)
    engine.delete_session(session.session_id)


asyncio.run(main())
```

The second request in `provider.requests` contains the first completed turn. The stream commits one
additional pair only after its final event.

## Future integration and current limitations

Stage 01.4 supplies an explicit, deterministic personality instruction through the existing session
boundary without moving personality rules into this engine. The selected instruction is preserved
between turns and after history clearing, while different sessions remain isolated. A future Memory
Engine may provide separately approved context, but persistent storage, retrieval, summaries, and
retention policy are not implemented here. Stage 01.6 uses `run_turn()` as a narrow public boundary:
the engine reserves the session, supplies selected textual context to an asynchronous operation,
and commits only its validated final text. Intermediate calls and results remain outside history.
Automatic model routing and real Ubuntu model validation remain separate roadmap work.
