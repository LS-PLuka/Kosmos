# Ubuntu Core Engine Validation

This is the maintainer-run validation procedure for Stage 01.8. Run it only on the prepared personal
Ubuntu host. Do not treat automated Windows or fake-provider results as real model evidence.

## Preparation

```bash
git switch develop
git pull --ff-only origin develop

uv lock --check
uv sync --frozen --dev

systemctl status ollama
systemctl show ollama --property=Environment

ollama list
curl http://127.0.0.1:11434/api/version
```

Confirm that the service environment includes `OLLAMA_NO_CLOUD=1`. A loopback endpoint alone does
not prove that the daemon performs no external processing. Confirm that
`qwen3.5:4b-q4_K_M` is installed and record its exact digest. Do not let the benchmark download a
model; it refuses to run a missing selection.

## Automated checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```

## Development CLI

```bash
uv run kosmos --help
uv run kosmos --version
uv run kosmos --list-models
uv run kosmos --effort instant --metrics
uv run kosmos --effort low --metrics
uv run kosmos --effort medium --metrics
uv run kosmos --effort high --metrics
```

Verify text conversation, streaming, context continuity, `/clear`, timeout recovery, cancellation,
and the visible distinction between successful, rejected, and failed tool results.

## Live benchmark

Review the catalog before authorizing inference:

```bash
uv run kosmos-benchmark --help
uv run kosmos-benchmark --list-scenarios
uv run kosmos-benchmark --suite quick --live --output benchmark-results/quick
uv run kosmos-benchmark --suite full --live --repetitions 3 --output benchmark-results/full
uv run kosmos-benchmark --suite performance --live --repetitions 3 --warm-up-runs 1 --output benchmark-results/performance
uv run kosmos-benchmark --suite quick --live --model qwen3.5:4b-q4_K_M
```

Review every `MANUAL_REVIEW` response. Record the number of samples alongside percentages. Do not
adjust criteria after seeing the results merely to obtain approval.

Confirm that reports from these commands say `Execution: LIVE`. `--live` is the required
authorization switch, while report provenance comes independently from the real local Ollama
execution path. Test reports created with fakes or HTTPX `MockTransport` must say
`Execution: SIMULATED` and are not real-model evidence.

## Resource observation

Run these in separate terminals while the live suite executes:

```bash
nvidia-smi
watch -n 1 nvidia-smi
ollama ps
watch -n 1 ollama ps
free -h
```

Record total and used VRAM, Ollama process memory when available, GPU utilization, temperature,
available RAM, loaded model, and GPU offload. Compare generation speed with the preliminary
44–48 tokens/s observation only when the workload and conditions are described; do not assume
equivalence. Never invent missing hardware measurements.

## Offline validation

Prepare the environment and model first. Confirm `OLLAMA_NO_CLOUD=1`, then disconnect the machine
from the internet. Do not probe external servers. With dependencies already synchronized, run:

```bash
uv run --offline --no-sync kosmos --list-models
uv run --offline --no-sync kosmos-benchmark --suite quick --live --output benchmark-results/offline-quick
```

Confirm normal conversation, streaming, pure tools, and report generation while disconnected.
Reconnect only after recording the result. The selected provider must remain the local loopback
Ollama adapter with no external fallback.

## Provisional engineering targets

- 100% deterministic authorization and security checks.
- 100% correct deterministic operations actually executed by Python.
- At least 90% basic tool selection across repeated samples.
- At least 90% correct communication of deterministic basic results.
- At least 90% basic contextual retention across repeated samples.
- Personality judged satisfactory by the maintainer.
- No critical failure blocking normal conversation.

These are initial engineering targets, not statistical claims about the model.

## Promotion checklist

- [ ] Automated tests passed.
- [ ] Required CI passed.
- [ ] Dependencies and lockfile are consistent.
- [ ] All 60 approved branding hashes are unchanged.
- [ ] Development CLI works on Ubuntu.
- [ ] Local Ollama and selected model are available.
- [ ] Complete inference and streaming work.
- [ ] Personality is recognizable and satisfactory.
- [ ] Conversation history and correction work.
- [ ] Pure tools execute and communicate correct results.
- [ ] No unauthorized handler execution occurred.
- [ ] Operational limits, timeout, and cancellation are safe.
- [ ] Performance and hardware observations were recorded.
- [ ] Offline operation was confirmed while disconnected.
- [ ] No critical failures remain.
- [ ] Problems identified: ________________________________________________
- [ ] Maintainer decision: PROMOTE / DO NOT PROMOTE / REPEAT VALIDATION
- [ ] Evidence location: _________________________________________________

Until every required item is reviewed, the status remains: **Benchmark infrastructure implemented.
Real model validation pending.**
