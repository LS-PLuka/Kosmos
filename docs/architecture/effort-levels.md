# Effort Levels

## Purpose

Effort is a trusted Kosmos execution policy, not a model permission and not an Ollama or Qwen
setting. It coordinates thinking, structured tool availability, inference and proposal limits, a
total deadline, and textual streaming. The caller selects the level explicitly; `LOW` is the
configurable default.

Thinking is only the provider-facing boolean control. Effort adds deterministic software limits
around provider work. No user message or model response can change a policy during a turn.

## Provisional defaults

| Level | Thinking | Tools | Inferences | Tool proposals | Deadline | Streaming |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `INSTANT` | disabled | disabled | 1 | 0 | 30 s | available |
| `LOW` | disabled | enabled | 3 | 2 | 60 s | textual only |
| `MEDIUM` | enabled | enabled | 5 | 4 | 120 s | textual only |
| `HIGH` | enabled | enabled | 8 | 8 | 240 s | textual only |

`INSTANT` targets greetings and direct explanations. `LOW` targets simple requests and pure
deterministic operations. `MEDIUM` supports bounded multi-step reasoning. `HIGH` provides larger
local reasoning and tool budgets, but does not activate web access, external providers, delegation,
or stronger authority.

`EXPERT` and `AUTO` are recognized reserved values. They raise an explicit
`UnsupportedEffortLevelError`; neither silently falls back to High. Expert delegation and automatic
classification remain future work.

## Validation and configuration

`EffortPolicy` is immutable. It rejects booleans used as integers, negative or unlimited counts,
non-finite or non-positive deadlines, and contradictory tool settings. Trusted application code
may inject a complete mapping of policies. Policies do not come from prompts, tool results, files,
environment variables, or model output.

Tool authorization is a separate intersection of registered, selected, explicitly allowed, and
`PURE` definitions. Increasing effort never expands that intersection. Defaults are provisional
engineering hypotheses; Stage 01.8 will measure real latency and quality before calibration.
