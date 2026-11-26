# Core Orchestration

## Status and responsibility

Stage 01.6 implements the provider-independent `CoreOrchestrator` on its feature branch. Automated
tests use fake providers; real Qwen behavior on Ubuntu remains pending. The orchestrator composes
the existing Personality Engine, Conversation Engine, provider ports, Tool Registry,
`ToolAuthorization`, and `ToolExecutor`. It does not replace them or own an Ollama lifecycle.

```text
trusted application request
  -> effort policy and explicit authorization
  -> reserved Conversation Engine turn
  -> integrated context budget
  -> text inference, or bounded structured tool loop
  -> final validated text
  -> atomic conversational commit
```

The public package `kosmos.core.orchestration` exports `CoreOrchestrator`, `EffortLevel`,
`EffortPolicy`, `OrchestrationContextPolicy`, `OrchestrationResult`, `OrchestrationStatus`,
`OrchestrationMetrics`, and `OrchestrationStream`.

## Sessions, personality, and atomicity

`create_session()` builds the official deterministic personality instruction once and passes it to
the Conversation Engine. That engine remains the sole session and confirmed-history owner. Its
`run_turn()` boundary reserves one session across all inference and tool awaits, supplies selected
text context to the coordinator, commits only the original user message and final assistant text,
and releases the session in `finally`.

Intermediate assistant proposals, arguments, results, and failures are operational context only.
Failure, timeout, or cancellation preserves prior history. Executed pure operations are not rolled
back. Clear, delete, and concurrent turns on a busy session remain rejected; different sessions are
independent.

## Provider and tool selection

Without an effective tool selection, the orchestrator uses `LLMProvider.generate()` and preserves
ordinary text inference. With effective tools, it requires the explicit or structurally detected
`ToolCallingProvider.generate_with_tools()` capability. There is no free-text parsing, provider
fallback, model-name inference, transport retry, or effort fallback.

Model-visible definitions preserve registry order and are the intersection of application
selection, execution-scoped authorization, and `PURE` risk. Blocked definitions are not announced.
The executor receives a second effective allowlist containing only that intersection, so a model
cannot broaden permission by naming another registered tool.

Calls execute sequentially in proposal order. Assistant call messages and correlated `TOOL`
results precede continuation. Text accompanying calls is intermediate and is never committed as a
final answer.

## Limits, context, and failures

Every started inference and every received proposal counts. A batch exceeding the remaining tool
budget is rejected before any handler in that batch executes. Calls proposed by the final permitted
inference are not executed because no continuation budget remains. Call identifiers must be unique
across the turn. Replay protection and idempotency across separate turns remain future work.

`OrchestrationContextPolicy` estimates compact serialized character size for system instruction,
confirmed history, current request, tool schemas, assistant calls, arguments, results, and required
metadata. It reserves generation space and removes only the oldest complete confirmed turns. It
never truncates required active data. If required context does not fit, it returns
`CONTEXT_LIMIT` before another provider call or tool execution. Character estimation is
deterministic but is not exact tokenization and cannot guarantee a provider's actual token window.

The total effort deadline covers coordination, inference, and tools. External cancellation
propagates. Timeout and cancellation are cooperative and cannot immediately interrupt a blocking
synchronous handler or internal Ollama generation. No background task, thread, process, or sandbox
is introduced.

Controlled terminal statuses distinguish completion, inference limit, tool limit, context limit,
timeout, provider unavailability, and invalid provider response. Provider-specific failures not
mapped by this contract continue to propagate. Tool failures remain structured results and may be
shown to the model for one bounded continuation; they are never changed into success.

## Metrics and streaming

Results include elapsed coordination seconds, started and completed inferences, proposals,
handlers invoked, successful tools, rejected or failed tools, effort, thinking, and the exact
available per-inference `InferenceMetrics`. Missing provider metrics are omitted rather than
invented or treated as zero. Provider nanosecond durations remain distinct from measured wall time.

`stream()` wraps the existing real `ConversationStream`, preserves Unicode and whitespace, applies
the total deadline during consumption, and commits only on a valid final event. It rejects an
effective structured-tool selection. Tool-call streaming is not implemented.

## Example

```python
orchestrator = CoreOrchestrator(provider, tool_registry=create_builtin_registry())
session = orchestrator.create_session()

calculation = await orchestrator.generate(
    session.session_id,
    "Quanto é 125 multiplicado por 32?",
    model="selected-model",
    effort=EffortLevel.LOW,
    authorization=ToolAuthorization(("calculate",)),
    selected_tools=("calculate",),
)

stream = orchestrator.stream(
    session.session_id,
    "Bom dia, Kosmos.",
    model="selected-model",
    effort=EffortLevel.INSTANT,
)
async for chunk in stream:
    print(chunk.content, end="")
```

A fake provider can first return `ToolCall("call_1", "calculate", ...)`, receive the structured
`{"result":4000}` tool result, and then return the final text. The result reports two inferences,
one proposal, one invoked handler, one success, and the confirmed final text. Multiple authorized
tools preserve proposal order. Empty authorization omits the definition and invokes no handler. An
oversized batch returns `TOOL_LIMIT`; required context overflow returns `CONTEXT_LIMIT`. These are
deterministic simulations, not validation of real Qwen selection or response quality.

## Security, lifecycle, and limitations

The permanent rule remains: **The AI interprets intent. The software validates and executes
operations.** Personality, effort, user text, calls, and tool results cannot grant permission.
Stage 01.6 supports only the two existing pure local tools and introduces no shell, file, process,
network, external provider, delegation, persistence, or logging of sensitive content.

The caller owns injected provider lifecycle and must close it. The orchestrator never loads a model,
opens an HTTP connection during import, or unexpectedly closes a shared provider. Automatic effort,
advanced tool streaming, external actions, cross-turn replay protection, semantic hallucination
detection, and real model validation remain outside this stage.
