# Tool Calling and Tool Registry

## Implementation status

Stage 01.5 implements provider-independent tool definitions, calls, results, deterministic argument
validation, an explicit registry, execution-scoped authorization, sequential execution, two pure
built-in tools, and native non-streaming Ollama tool calling. R4 refines model-visible definitions
and composes trusted turn-scoped operational guidance from effective availability. Automated tests
use fakes and HTTPX `MockTransport`; real Qwen behavior on the target Ubuntu host remains pending.

Stage 01.6 composes these unchanged contracts into automatic bounded orchestration. Stage 01.5
remains independently usable for explicit manual composition.

## Effective availability and delegation

Registry presence is not availability. The Core Orchestrator advertises only the intersection of
registered, selected, execution-authorized, `PURE`, effort-enabled tools. A provider must also
support structured tool calling or the selected tool flow is rejected before inference.

For every request, R4 appends a compact trusted instruction to the system content sent to the
provider. It states whether tools are disabled by effort, unavailable for the turn, or effectively
available by name. When tools are available, it asks the model to prefer a matching deterministic
tool for operational requests, avoid tools for conceptual or unrelated conversation, perform
dependent operations sequentially from returned results, treat results as data, and communicate
failures honestly. It does not duplicate schemas, grant permission, mutate the session instruction,
or become user history. Complete text, streaming text, and structured requests all budget it before
provider inference.

This guidance improves the conditions for model selection but cannot guarantee compliance. Only a
structured proposal followed by executor evidence proves that a tool was attempted or executed.

## Architectural boundaries

The permanent rule is: **The AI interprets intent. The software validates and executes
operations.** A `ToolCall` is untrusted input. Registration, risk classification, authorization,
argument validation, handler selection, and result validation are owned by trusted Python code.

The `ToolCallingProvider` capability is separate from `LLMProvider`. Text-only providers do not
need to support tools. `OllamaProvider` implements both ports but does not import the registry or
executor and never executes a handler. The Conversation Engine and Personality Engine remain
unchanged; callers may manually include an existing personality instruction as a system tool
message.

## Public contracts

- `ToolParameter` describes one supported value and produces its provider schema.
- `ToolDefinition` contains public metadata, parameters, and trusted risk classification.
- `ToolCall` contains a locally generated correlation identifier, tool name, and deeply frozen
  arguments.
- `ToolResult` distinguishes success, unknown tools, invalid arguments, denial, execution failure,
  and timeout. Stage 01.5 does not impose an executor timeout, so it does not produce timeout
  results itself.
- `ToolMessage`, `ToolInferenceRequest`, and `ToolInferenceResponse` represent structured tool
  conversations independently of Ollama.
- `ToolRegistry`, `ToolAuthorization`, and `ToolExecutor` provide registration, policy, and
  execution boundaries.

Definitions and calls use immutable dataclasses. Mutable JSON containers are recursively copied
into read-only mappings and tuples. Returned handler arguments are separate mutable copies, so a
handler cannot mutate a validated call.

## Parameter schema and validation

The supported JSON Schema subset contains string, integer, number, boolean, and array parameters;
required fields; explicit enums; numeric minimum and maximum; string length limits; array size
limits; and array item schemas. Object parameters are intentionally omitted because neither
approved built-in requires them. The implementation is not a general JSON Schema interpreter.

`ToolParameter.to_schema()` is the single source for provider schemas, while the same parameter
objects drive `validate_arguments()`. Validation rejects missing required fields, unknown fields,
type coercion, booleans used as numbers, non-finite numbers, values outside bounds, invalid enum
values, oversized arrays and strings, non-JSON values, and nesting deeper than eight container
levels.

## Registry, risk, and authorization

Each `ToolRegistry` is explicitly constructed. Registration associates one definition with one
trusted handler, rejects duplicate names, preserves registration order, and never exposes handlers
in provider schemas. Imports do not register tools, and no dynamic discovery or global mutable
registry exists.

Risk classifications are `PURE`, `READ_ONLY`, `SIDE_EFFECT`, and `SENSITIVE`. Only `PURE` tools can
execute in Stage 01.5, and even pure tools require their exact name in an execution-scoped
`ToolAuthorization`. Registration and presentation to a model do not grant permission. All other
classifications remain blocked even if their names are placed in an allowlist.

## Execution

`ToolExecutor.execute()` performs these steps in order:

1. Locate the registered definition and handler.
2. Check the trusted authorization policy.
3. Validate and detach arguments.
4. Invoke the registered synchronous or asynchronous handler once.
5. Validate JSON serialization and the output-size limit.
6. Return a structured, safe `ToolResult`.

Unknown, denied, or invalid calls never invoke a handler. There are no retries, subprocesses,
parallel execution, background tasks, or automatic recovery. Cancellation propagates. Handler
exceptions are converted to a generic result without stack traces, local paths, arguments, or
private exception text.

The executor is not a sandbox. Cooperative asynchronous cancellation cannot interrupt arbitrary
blocking synchronous code. Timeouts, replay protection, cross-execution deduplication, and
idempotency policy are deferred until tools with external effects have concrete requirements.

## Built-in tools

`create_builtin_registry()` returns a fresh registry with exactly two tools. R4 descriptions state
when each tool is appropriate and clarify operand or item meaning without embedding authorization:

- `calculate` supports `add`, `subtract`, `multiply`, and `divide`. Inputs are finite integers or
  binary floating-point numbers from `-10^12` through `10^12`; booleans and implicit conversions
  are rejected. Results must remain finite and at most `10^15` in absolute value. Integer
  addition, subtraction, and multiplication remain integers; division follows Python binary
  floating-point behavior. Division by zero and excessive results fail safely. No expression
  evaluation is used.
- `count_items` counts zero through 1,000 strings, each no longer than 200 characters. It performs
  no external access.

`calculate` uses ordinary Python integer and binary floating-point arithmetic. It does not promise
arbitrary mathematical precision or freedom from floating-point representation and rounding
limitations.

## Native Ollama integration

`OllamaProvider.generate_with_tools()` uses `POST /api/chat`, `stream: false`, and the native
`tools` field. It preserves the existing loopback-only client, HTTPX lifecycle, configured context,
thinking, keep-alive, metrics, timeout mapping, proxy exclusion, and redirect exclusion.

The adapter accepts assistant text, ordered structured calls, or both. It rejects malformed
messages, non-object arguments, empty responses, more than eight calls, and arguments larger than
8,192 UTF-8 JSON bytes per call. Ollama does not provide the OpenAI call identifier contract, so
Kosmos generates a unique local identifier for every parsed call. Text that merely resembles JSON
or a function call is never parsed as an executable proposal.

For continuation, the prior response becomes an assistant message containing native
`tool_calls`. `ToolMessage.from_result()` produces a `role: tool` message with `tool_name` and a
compact JSON result payload. Local `call_id` remains in that payload for application correlation;
the adapter does not invent an Ollama protocol field.

An effective request schema for `calculate` is:

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Perform one deterministic basic arithmetic operation.",
    "parameters": {
      "type": "object",
      "properties": {
        "operation": {
          "type": "string",
          "description": "Arithmetic operation.",
          "enum": ["add", "subtract", "multiply", "divide"]
        },
        "a": {
          "type": "number",
          "description": "First finite operand.",
          "minimum": -1000000000000,
          "maximum": 1000000000000
        },
        "b": {
          "type": "number",
          "description": "Second finite operand.",
          "minimum": -1000000000000,
          "maximum": 1000000000000
        }
      },
      "required": ["operation", "a", "b"],
      "additionalProperties": false
    }
  }
}
```

## Explicit composition example

```python
first_request = ToolInferenceRequest(
    model="qwen3.5:4b-q4_K_M",
    messages=(ToolMessage(ToolMessageRole.USER, "Multiply 125 by 32."),),
    tools=(CALCULATE_DEFINITION,),
)
proposal = await provider.generate_with_tools(first_request)

executor = ToolExecutor(create_builtin_registry())
authorization = ToolAuthorization(("calculate",))
result = await executor.execute(proposal.tool_calls[0], authorization)

continuation = ToolInferenceRequest(
    model=first_request.model,
    messages=(
        *first_request.messages,
        proposal.as_message(),
        ToolMessage.from_result(result),
    ),
    tools=first_request.tools,
)
final_response = await provider.generate_with_tools(continuation)
```

With `ToolAuthorization()` the same proposal produces `UNAUTHORIZED`, and the handler is not
called. Tests demonstrate both paths with a fake provider. These simulations validate software
boundaries, not the Qwen model's real ability to choose tools.

## Limits, security, and future work

Tool calls allow at most eight proposals per Ollama response, 8,192 argument bytes per call, and
eight JSON container levels. Results allow 16,384 UTF-8 JSON bytes. Only explicitly selected tools
are sent to a provider. These are technical resource and context protections, not commercial
limits. Character and byte counts are not guaranteed token counts, and Stage 01.5 does not change
the existing context policy or 4,096-token Ollama configuration.

Core orchestration performs integrated-context preflight after receiving a proposal and before
each handler in a batch. Proposal arguments and earlier results are then known and count toward the
required active turn. If that known data cannot fit after eligible confirmed history is removed,
remaining calls are not executed. The software cannot predict a handler result before execution;
an already produced result is retained as evidence even when it prevents continuation.

There is no shell, file, process, application, device, credential, network, remote, or arbitrary
code tool. Results are untrusted data and do not become system instructions. Stage 01.6 owns
integrated context budgeting and explicit orchestration without inferring authorization from
personality text, user language, or model output.
