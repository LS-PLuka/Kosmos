# Wake Word Detection

Stage 02.5 adds independent wake-word infrastructure for the institutional phrase **Kosmos**, with
the natural Brazilian Portuguese pronunciation of the Portuguese word "cosmos". The infrastructure,
backend adapter, deterministic policy, diagnostics, and simulated validation are implemented. No
approved Kosmos classifier exists, and real detection is not validated or production-ready.

## Boundary and architecture

```text
AudioChunk -> WakeWordFramer -> openWakeWord-compatible ONNX pipeline -> score
                                                                     |
score + acoustic frame -> WakeWordActivationPolicy -> WakeWordDetection
```

The detector computes a score. The policy interprets validated scores and emits at most one event
per confirmed occurrence. Neither component opens a microphone, invokes VAD, STT, TTS, Qwen, Core,
or a tool. A wake word starts a future interaction; it does not identify, authenticate, or authorize
a person. Stage 02.6 will own orchestration.

Public contracts contain no NumPy or ONNX Runtime types. `WakeWordDetector` exposes explicit load,
ordered evaluation, reset, close, state, and metrics operations. `WakeWordResult` identifies the
scored 80 ms window and whether warm-up is complete. `WakeWordDetection` records the phrase, model
identifier, validated score, and confirmation frame. It does not claim word onset or offset.

## Technology decision and compatibility

Strategy A, `openwakeword==0.6.0`, was rejected as a runtime dependency. Its published metadata
requires `tflite-runtime>=2.8,<3` on Linux, while the published TFLite Runtime 2.14 wheels support at
most CPython 3.11. Installing the package therefore cannot satisfy Python 3.12 on both Windows and
Ubuntu. Pull request 216 discusses moving runtime choices to extras, but it is unmerged and is not
part of the published release.

Strategy B is implemented as a small direct ONNX adapter based on openWakeWord v0.6.0, commit
`c8ef691`. It uses only NumPy `>=2.0,<3` and ONNX Runtime `1.32.0`, already resolved for other voice
extras. The adapter is not a copy of the library and does not import it. Apache-2.0 attribution
applies to the upstream algorithmic reference. Real equivalence with the reference pipeline is
pending because Kosmos has neither downloaded the auxiliary models nor run real inference.

The `wakeword` extra directly declares NumPy and ONNX Runtime. It is independent of `voice`, `stt`,
and `vad`. ONNX sessions use only `CPUExecutionProvider`, one intra-op thread, one inter-op thread,
and sequential execution. Python 3.12 Windows and Linux x86-64 wheels exist in the selected lock
resolution; execution on Ubuntu remains unvalidated.

## Local artifacts and provenance

The adapter requires three explicit absolute local `.onnx` paths:

- an openWakeWord-compatible melspectrogram model;
- the compatible Google speech-embedding model export;
- a binary classifier actually trained for the intended Kosmos pronunciation.

Each file must be regular, non-empty, at most 32 MiB, and optionally match a configured lowercase
SHA-256. Sessions are constructed only after all files validate. There is no automatic download,
built-in-model selection, URL, TFLite fallback, internal Silero VAD, or substitute wake word. A hash
establishes file identity, not origin, consent, quality, or legal permission.

The openWakeWord code is Apache-2.0. Its published pretrained classifiers are documented separately
under CC BY-NC-SA 4.0. Auxiliary feature-model provenance and redistribution terms require exact
artifact review. A custom classifier's terms depend on its training data, voices, generators, and
feature sources; it is not automatically Apache-2.0. The provisional Razo voice must not be used to
generate training data until provenance and permissions are resolved.

## PCM, framing, and pipeline

Input is mono 16,000 Hz signed 16-bit little-endian PCM. There is no resampling, downmix, noise
suppression, gain control, or echo cancellation. `WakeWordFramer` accepts variable `AudioChunk`
sizes, preserves order and every sample, emits exact 1,280-sample (80 ms) windows, retains at most
one incomplete window, and tracks absolute frame offsets. Final residual PCM is returned without
padding or inference. A discontinuity fails explicitly and requires reset.

For each complete window, the pinned pipeline:

1. passes float32 PCM values in the original int16 numeric scale to the melspectrogram session,
   including up to 480 prior samples;
2. applies the pinned `melspectrogram / 10 + 2` transformation;
3. keeps a bounded 76-by-32 spectral context and produces one 96-value embedding;
4. keeps at most 120 embeddings and passes the classifier's declared fixed temporal context as a
   `[1, context, 96]` float32 tensor;
5. accepts only one finite `[1, 1]` score from zero through one, without adding sigmoid or softmax.

The adapter validates the known feature contracts and reads the classifier context length from its
metadata rather than assuming one classifier shape. Input/output names for feature models follow
the pinned release (`input` and `input_1`); the classifier input name is read from the model.
Classifier scores are ranking signals, not calibrated statistical probabilities.

Buffers are bounded to ten seconds of raw PCM, 970 spectral frames, and 120 embeddings. Audio and
score histories are not persisted. Each detector owns one sequence and three sessions. A
non-blocking lock rejects concurrent load, inference, reset, or close. Native inference is
synchronous and must not run in a physical capture callback. A failure marks the sequence failed;
reset is required. Close releases session references and forbids later inference.

## Warm-up and activation policy

The pinned openWakeWord release suppresses its first five predictions. Kosmos exposes the same
five-frame provisional warm-up explicitly: scores remain observable in structured results but the
policy cannot emit events until readiness. Reset starts a new warm-up. This value must be reviewed
if the selected classifier or reference revision changes.

The default policy uses inclusive comparisons: two consecutive ready scores at or above `0.50`
confirm an activation. Any lower score before confirmation cancels the candidate. Confirmation
emits exactly one event at the end frame of the confirming window and enters a two-second cooldown
measured in acoustic frames, never wall time or `sleep`.

After cooldown, the policy remains in rearm until a score is at or below `0.30`. Persistently high
scores are suppressed and cannot create duplicate events. The low rearm frame does not itself start
a new candidate. Discontinuity resets confirmation, cooldown, and rearm state. Thresholds,
confirmation count, cooldown, and rearm are provisional and require Stage 02.8 calibration.

## Configuration

| Variable | Default |
| --- | --- |
| `KOSMOS_WAKEWORD_ENABLED` | `false` |
| `KOSMOS_WAKEWORD_BACKEND` | `openwakeword-onnx` |
| `KOSMOS_WAKEWORD_PHRASE` | `Kosmos` |
| `KOSMOS_WAKEWORD_MODEL_IDENTIFIER` | `kosmos` |
| `KOSMOS_WAKEWORD_MODEL_PATH` | unset |
| `KOSMOS_WAKEWORD_MELSPECTROGRAM_PATH` | unset |
| `KOSMOS_WAKEWORD_EMBEDDING_MODEL_PATH` | unset |
| `KOSMOS_WAKEWORD_MODEL_SHA256` | unset |
| `KOSMOS_WAKEWORD_MELSPECTROGRAM_SHA256` | unset |
| `KOSMOS_WAKEWORD_EMBEDDING_MODEL_SHA256` | unset |
| `KOSMOS_WAKEWORD_THRESHOLD` | `0.50` |
| `KOSMOS_WAKEWORD_REARM_THRESHOLD` | `0.30` |
| `KOSMOS_WAKEWORD_CONFIRMATION_FRAMES` | `2` |
| `KOSMOS_WAKEWORD_COOLDOWN_SECONDS` | `2` |

Configuration loading has no file, model, dependency, network, device, or inference side effect.
Enabling detection is not permission to open a microphone; physical capture also requires
`KOSMOS_VOICE_ENABLED=true` and an explicit bounded diagnostic command.

## Diagnostics, metrics, and future handoff

```bash
uv sync --frozen --dev --extra wakeword
uv run --no-sync kosmos-wakeword status
uv run --no-sync kosmos-wakeword models
uv run --no-sync kosmos-wakeword analyze --file sample.wav
uv run --no-sync kosmos-wakeword listen --duration 5
```

`status` imports optional packages but does not read models, create sessions, infer, or open a
device. `models` reports configured paths without printing private paths. `analyze` accepts a local
compatible PCM WAV up to five minutes. `listen` is explicit, requires both model validation and
Voice Foundation authorization, captures at most 30 seconds, and processes only after capture.

Metrics report model identity, frames processed, inference count, completed warm-up frames, load
and inference durations, and inference real-time factor. They do not claim accuracy, acoustic
latency, false acceptance rate, or false rejection rate.

Absolute offsets let a future orchestrator retain recent PCM and hand subsequent speech to VAD/STT
without starting a new capture at detection time. This stage does not store continuous audio,
remove the wake word, infer its boundaries, or discard later samples. Stage 02.6 must define that
handoff. TTS can self-trigger on the word Kosmos; playback suppression and echo behavior belong to
Stage 02.7, not this detector.

## Validation status

Automated tests use synthetic PCM, fake ONNX sessions, controlled tensor outputs, and deterministic
scores. They cover model/config validation, framing, offsets, transforms, warm-up, invalid scores,
confirmation, cooldown, rearm, duplicate suppression, lifecycle, and diagnostics. They do not
validate an auxiliary model, a Kosmos classifier, Brazilian Portuguese accuracy, microphones,
physical continuity, offline operation, performance, thresholds, Windows/Ubuntu inference, or
licensing of future artifacts.
