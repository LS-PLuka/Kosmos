# Core Orchestration

## Status and responsibility

Stage 01.6 implements the integrated provider-independent `CoreOrchestrator`. Automated
tests use fake providers; real Qwen behavior on Ubuntu remains pending. The orchestrator composes
the existing Personality Engine, Conversation Engine, provider ports, Tool Registry,
`ToolAuthorization`, and `ToolExecutor`. It does not replace them or own an Ollama lifecycle.

```text
trusted application request
  -> effort policy and explicit authorization
  -> reserved Conversation Engine turn
  -> turn-scoped effective-tool guidance
  -> integrated context budget
  -> text inference, or bounded structured tool loop
  -> final validated text
  -> atomic conversational commit
```

The public package `kosmos.core.orchestration` exports `CoreOrchestrator`, `EffortLevel`,
`EffortPolicy`, `OrchestrationContextPolicy`, `OrchestrationResult`, `OrchestrationStatus`,
`OrchestrationMetrics`, `ContextMetrics`, `ContextRequestMetrics`, and `OrchestrationStream`.

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

The R4 operational instruction is composed anew for every turn and appended only to the transient
provider request. It is never written into `ConversationSession.system_instruction` or confirmed
history, so changing effort, selection, or authorization cannot leave stale capability claims.

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

Dependent operations are expected across successive inferences: the next proposal can then use the
actual correlated result from the previous execution. The guidance explicitly prohibits treating
an invented intermediate value as confirmed. Calls in one provider batch remain ordered; the
software does not infer semantic dependencies from argument text.

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

R3 keeps the 12,000-character integrated limit and 2,000-character response reserve, producing a
10,000-character serialized input budget. Conversation selection runs first with its 8,000 content
budget. The integrated text and tool paths then measure compact serialization and may remove more
oldest complete confirmed turns when framing or tool schemas require space. Complete generation and
streaming use the same integrated fitting operation. Structured tool inference repeats it before
every provider call because assistant calls and tool results enlarge the active turn. After each
structured proposal, the orchestrator also performs a preflight before every handler invocation.
This uses all arguments and earlier results already known in the batch, so a tool is not invoked
when the required continuation has already become impossible within the declared budget. Unknown
future result size cannot be predicted; a result that alone exhausts the budget remains preserved
as execution evidence and prevents later calls or inference.

System instruction, transient operational guidance, current user message, selected schemas,
assistant calls, and correlated tool results are mandatory. If they do not fit after all eligible
prior history is removed, the next inference is not started. A tool already executed is not rolled
back: its `ToolResult` remains in
the controlled result as evidence, while the uncompleted conversational turn remains unconfirmed.

The total effort deadline covers coordination, inference, and tools. External cancellation
propagates. Timeout and cancellation are cooperative and cannot immediately interrupt a blocking
synchronous handler or internal Ollama generation. No background task, thread, process, or sandbox
is introduced.

Controlled terminal statuses distinguish completion, inference limit, tool limit, context limit,
orchestration timeout, provider timeout, provider HTTP failure, provider unavailability, invalid
provider response, and other inference failure. These controlled results preserve proposal and tool
result evidence accumulated before a final inference failure. Tool failures remain structured
results and may be shown to the model for one bounded continuation; they are never changed into
success.

## Metrics and streaming

Results include elapsed coordination seconds, started and completed inferences, proposals,
handlers invoked, successful tools, rejected or failed tools, effort, thinking, and the exact
available per-inference `InferenceMetrics`. Missing provider metrics are omitted rather than
invented or treated as zero. `inference_metric_indices` correlates every available optional metric
with the inference that produced it, so an absent earlier value cannot shift later presentation or
reporting. Provider nanosecond durations remain distinct from measured wall time.

`OrchestrationResult.tool_calls` preserves immutable structured proposals, including rejected or
over-budget proposals, separately from `tool_results`. Arguments are intentionally absent from
content-free metrics. Callers can distinguish a textual mention, a proposal, a handler invocation,
an execution failure, and a successful result without trusting final prose.

R3 also exposes immutable, content-free context metrics. `ContextMetrics.conversation` records the
initial content-only selection. Each `ContextRequestMetrics` entry records request kind, integrated
character budget, selected message characters, compact serialized request characters, response
reserve, and turns omitted specifically by the integrated stage. Tool turns can therefore expose
one entry per attempted inference. Metrics are absent only when selection could not be measured
before failure; they never log prompts, message content, or personal data.

`stream()` wraps the existing real `ConversationStream`, preserves Unicode and whitespace, applies
the total deadline during consumption, and commits only on a valid final event. It rejects an
effective structured-tool selection. Tool-call streaming is not implemented.
The returned `OrchestrationStream.context_metrics` exposes the selection made synchronously before
provider streaming begins. R5 consumes this public measurement in the CLI; the Core remains
independent from terminal formatting, clocks used for presentation latency, `argparse`, and I/O.

## Interface readiness

Future interfaces can create, inspect, clear, and delete sessions through the public orchestrator;
await complete generation; consume textual streaming; cancel tasks; handle controlled statuses;
and read content-free metrics without depending on the development CLI. This boundary is suitable
for a future voice presentation layer and introduces no dependency from Core to audio, terminal, or
GUI code.

Stage 02 still needs its own capture, recognition, synthesis, VAD, wake-word, playback,
backpressure, interruption, and capture-versus-playback coordination. Structured tool calling is
non-streaming, and no current metric represents time to first audible output. These are planned
voice concerns, not regressions or reasons to add audio contracts to Stage 01.

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

Stage 01.8 applies the same integrated orchestration context budget to complete and streaming text
requests before provider inference. The CLI recovers from streaming context-limit errors without
discarding confirmed history and presents statuses only from real `ToolResult` evidence. The
benchmark reuses this public orchestration boundary; it does not duplicate session or execution
logic.

## Security, lifecycle, and limitations

The permanent rule remains: **The AI interprets intent. The software validates and executes
operations.** Personality, effort, user text, calls, and tool results cannot grant permission.
Stage 01.6 supports only the two existing pure local tools and introduces no shell, file, process,
network, external provider, delegation, persistence, or logging of sensitive content.

The caller owns injected provider lifecycle and must close it. The orchestrator never loads a model,
opens an HTTP connection during import, or unexpectedly closes a shared provider. Automatic effort,
advanced tool streaming, external actions, cross-turn replay protection, semantic hallucination
detection, and real model validation remain outside this stage.
