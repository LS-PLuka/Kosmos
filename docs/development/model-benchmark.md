# Model Benchmark and Validation

## Status

Stage 01.8 provides a reproducible evaluation harness for the existing Core Engine. The harness is
implemented and automatically tested with fake providers and HTTPX `MockTransport`. Real Qwen
validation on the target Ubuntu hardware remains pending. Results never promote the Core Engine
automatically; the maintainer owns the final decision.

## Architecture

The `kosmos.benchmarking` package defines immutable scenarios, named suites, evidence-based
evaluation, a runner, and terminal/JSON/Markdown reporting. The runner creates a new public
`CoreOrchestrator` session for every repetition and keeps only the turns belonging to one scenario
in that session. It reuses the registered pure tools, authorization, effort policies, conversation
management, context policies, metrics, and provider adapter. It does not implement another
orchestrator or bypass deterministic execution.

Importing the package has no runtime side effects. Help and scenario listing do not initialize
Ollama. Any inference through the command entry point requires the explicit `--live` flag and an
installed model selected through the same configuration precedence as the development CLI.

Authorization and provenance are separate. `--live` authorizes the real entry point to begin local
inference, but does not by itself label results. Reports produced by the real entry point with the
local Ollama provider are marked `LIVE`. Reports produced by fake providers or HTTPX
`MockTransport` are marked `SIMULATED`, including when a test exercises the authorized execution
path.

## Commands

```bash
uv run kosmos-benchmark --help
uv run kosmos-benchmark --list-scenarios
uv run kosmos-benchmark --suite quick --live
uv run kosmos-benchmark --suite full --live
uv run kosmos-benchmark --suite performance --live
uv run kosmos-benchmark --suite quick --live --model qwen3.5:4b-q4_K_M
```

Full defaults to three measured repetitions. Quick defaults to one. Performance defaults to one
warm-up and one measured repetition per selected scenario. Override them explicitly:

```bash
uv run kosmos-benchmark --suite full --live --repetitions 3
uv run kosmos-benchmark --suite performance --live --repetitions 3 --warm-up-runs 1
uv run kosmos-benchmark --suite performance --live --efforts instant low medium high
```

Three samples improve repeatability checks but are not broad statistical evidence. Warm-ups are
identified, retained in reports as `SKIPPED`, and excluded from primary statistics. A warm-up does
not prove that the model was previously unloaded, and the benchmark never unloads models or clears
hardware caches.

## Suites and scenarios

- **Quick** checks identity, greeting, context recall, multiplication, item counting, uncertainty,
  and truthful capability boundaries.
- **Full** covers personality, conversation, tool calling, accuracy, reasoning, security, context,
  stability, and the Core Engine operational boundaries.
- **Performance** measures short and medium answers, streaming time to first non-empty text, tool
  inference, thinking disabled and enabled, and the four supported effort levels.

`uv run kosmos-benchmark --list-scenarios` is the authoritative versioned catalog. Prompts use only
fictional or generic data. Multi-turn scenarios share one session; repetitions never do. Automated
tests separately verify session clearing, isolation, authorization, call limits, cancellation,
provider closure, and malformed transport responses without asking a model to attest to internal
state.

## Evaluation

Statuses are `PASS`, `FAIL`, `ERROR`, `SKIPPED`, and `MANUAL_REVIEW`.

Deterministic tool scenarios evaluate three independent facts: the expected tool produced a real
`ToolResult`, Python execution returned the expected value, and the final model response
communicated that value. A numerically correct sentence without execution fails tool selection. A
correct tool result with an incorrect sentence fails result communication.

Conversation factual checks use documented, scenario-specific text heuristics. They are useful
signals, not semantic proof. Naturalness, elegance, humor, sophistication, disagreement quality,
and open-ended explanations always require human review. `MANUAL_REVIEW` is excluded from the
deterministic pass count. No external LLM judge, API, general-intelligence score, or paid service is
used.

## Metrics

Reports reuse `OrchestrationMetrics` and `InferenceMetrics` and include available elapsed time,
first non-empty streaming text, provider durations, prompt tokens, generated tokens, inference
counts, tool proposals, handler executions, successful tools, and rejected or failed tools. Values
that the provider does not supply remain unavailable.

R3 adds internal `ContextMetrics` to orchestration results. They distinguish initial conversation
omissions caused by the turn and content-character limits from later omissions caused by compact
serialized requests, tool schemas, calls, and results. They contain counts and sizes only. Existing
terminal, JSON, and Markdown presentation remains unchanged for report comparability; visible
context diagnostics are deferred to R5.

Generation speed is calculated only for positive reported generation duration:

```python
tokens_per_second = eval_count / (eval_duration_ns / 1_000_000_000)
```

Multiple inference rates use summed token counts and summed generation durations. Software elapsed
time, provider total duration, prompt evaluation, model loading, and generation remain distinct.

## Reports and reproducibility

Export is opt-in and refuses to overwrite either file:

```bash
uv run kosmos-benchmark --suite quick --live --output benchmark-results/quick-01
```

This creates `quick-01.json` and `quick-01.md`. Local `benchmark-results/` is ignored by Git. The
report records explicit `LIVE` or `SIMULATED` provenance, Kosmos, Python, operating system, Ollama,
model identifier and digest, context configuration, effective effort policies, repetitions,
warm-ups, scenario version, and UTC start time. It does not collect complete environment variables,
credentials, hostnames, or hardware identity. Model responses are not claimed to be bit-for-bit
reproducible.

## Limitations

Character budgets are conservative software limits, not a model-specific tokenizer guarantee.
The harness does not change `num_ctx`, temperature, seed, model residency, Ollama configuration, or
network state. Hardware utilization is observed manually. The benchmark is specific to Kosmos Core
behavior and does not measure general intelligence. Real model quality, offline operation,
performance, personality, and hardware fit remain pending until the maintainer completes the
[Ubuntu validation](ubuntu-validation.md).

The existing full-suite `multiple_fact_recall`, `context_correction`, and `long_context_response`
scenarios remain semantically unchanged, so historical catalogs are comparable. R3 automated
regressions inspect fake-provider request messages directly; benchmark text heuristics remain model
quality signals and are not treated as proof of software-side retention.
