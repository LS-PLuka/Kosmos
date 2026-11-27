# Voice Activity Detection

Stage 02.4 adds independent local voice-activity estimation and deterministic speech segmentation.
It does not open a microphone automatically, transcribe audio, invoke Qwen, play Piper output,
identify a speaker, detect a wake word, or authorize an operation. Automated tests use fake ONNX
sessions, synthetic PCM, and predefined probabilities. Real model, microphone, offline,
performance, threshold, and Brazilian Portuguese validation remain pending.

## Boundary and architecture

```text
AudioChunk -> AudioFramer -> VoiceActivityDetector -> probability
                                           |
AudioWindow + probability -> SpeechSegmenter -> events + Utterance
```

Detection estimates speech probability for one model window. Segmentation interprets ordered
probabilities over the acoustic timeline. Speech-to-text converts a completed utterance to text;
wake-word detection matches an activation phrase; speaker recognition attempts identity. These are
separate responsibilities. Stage 02.4 implements only the first two.

Public models and ports contain no ONNX Runtime, NumPy, Silero, Faster Whisper, SoundDevice, Piper,
Ollama, or Qwen types. `AudioChunk`, `AudioFormat`, and `SampleFormat` remain the shared PCM
contracts. `Utterance.audio` is directly compatible with a future `SpeechRecognitionRequest`, but
the VAD package does not import or call STT.

## Selected model and runtime

The conservative reference is Silero VAD v6.2.3, tag commit
`5cd7945676eb32225748052e2e6a0580e4686a08`, file
`src/silero_vad/data/silero_vad.onnx`. A local installation may rename it
`silero-vad-v6.2.3.onnx`. The cited SHA-256 is
`1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3`; the byte-identical file is
2,327,524 bytes. Kosmos did not download the model, so neither value has been verified locally.

The upstream [v6.2.3 release](https://github.com/snakers4/silero-vad/releases/tag/v6.2.3),
[pinned wrapper](https://github.com/snakers4/silero-vad/blob/5cd7945676eb32225748052e2e6a0580e4686a08/src/silero_vad/utils_vad.py),
and [model-license answer](https://github.com/snakers4/silero-vad/discussions/817) establish the
revision, recurrent contract, cited checksum, and MIT statement. The exact byte size was
cross-checked against independent byte-identical mirrors. This is provenance evidence, not a local
integrity check.

Silero v6.3 was reviewed. It keeps the API and tensor names but changes model behavior, is slightly
stricter at the same threshold, and explicitly requires threshold re-evaluation. Stage 02.4 retains
v6.2.3 until real calibration can justify promotion. Sequence, ifless, half, OpenVINO, and op15
exports are different artifacts and are not accepted as substitutes without a new review.

The `vad` extra directly requires NumPy `>=2.0,<3` and ONNX Runtime `1.32.0`. The resolved versions
are NumPy 2.5.5 and ONNX Runtime 1.32.0. Both publish CPython 3.12 wheels for Windows and Linux
x86-64. ONNX Runtime and Silero are MIT; NumPy is BSD-3-Clause. Native runtime and transitive
notices still require exact-artifact review before redistribution. Kosmos installs neither PyTorch
nor the `silero-vad` Python package.

## PCM, framing, and conversion

Input is strictly mono, 16,000 Hz, signed 16-bit little-endian PCM. There is no resampling or
downmix. The framer accepts variable `AudioChunk` sizes, preserves order and every real sample,
emits 512-sample windows, retains at most one incomplete window, and tracks absolute frame offsets.
An explicit offset mismatch fails as a discontinuity and requires reset.

At stream finalization, a residual window is zero-padded only through `AudioWindow.inference_pcm`.
The real `AudioChunk`, its duration, segment timestamps, and returned utterance never contain the
synthetic padding. PCM conversion uses little-endian `int16`, casts to `float32`, and divides by
32768.0. Conversion stays inside the adapter so the Voice Foundation does not require NumPy.

## ONNX tensor contract and lifecycle

At 16 kHz, each 512-sample frame is prefixed with the previous 64 normalized samples. The effective
input is float32 `[1, 576]`. The first context is zero. `state` starts as float32 `[2, 1, 128]` and
the returned `stateN` becomes the next state. `sr` is scalar int64 `16000`; `output` must be
float32-compatible `[1, 1]` with one finite probability from zero through one.

Context and recurrent state are updated only after both outputs validate. A failure marks the
sequence failed; it is never converted to silence, and reset is required. Reset clears context,
state, timeline, and per-sequence counters while retaining the loaded session. Close releases
references and forbids later operations. Each detector owns one session and one sequence; there is
no global singleton or shared buffer.

Loading is explicit or lazy on first explicit evaluation. The adapter pins
`CPUExecutionProvider`, one intra-op thread, one inter-op thread, and sequential execution. Its API
is synchronous because each window is short, but it is blocking native work and must not run in a
physical capture callback. A non-blocking lock rejects concurrent load, inference, reset, or close.
No thread, queue, download, telemetry, or background task is created.

## Deterministic segmentation

The segmenter uses frame counts, never wall-clock time. Its states are `IDLE`, `POSSIBLE_SPEECH`,
`SPEECH_ACTIVE`, and `POSSIBLE_END`.

- A probability greater than or equal to 0.50 contributes to consecutive speech confirmation.
- A value less than or equal to 0.35 contributes to confirmed silence.
- The intermediate band preserves the active or possible-end state but contributes to neither
  confirmation counter.
- Before speech confirmation, any value below 0.50 cancels the candidate.
- A value at or above 0.50 cancels a possible end and resumes active speech.

The provisional defaults require 160 ms of speech and 640 ms of silence. Candidate audio is kept,
so confirmation does not remove the beginning. A bounded 256 ms pre-roll protects earlier onset.
Only up to 128 ms after the estimated acoustic end is retained as post-roll; the remaining silence
used for confirmation stays outside the utterance and may become pre-roll for the next candidate.
High minimum-speech values can reject short words and require real calibration.

Every utterance includes pre-roll, confirmed speech, preserved internal pauses, and post-roll in
its 30-second total limit. A boundary at 480,000 real frames is exact even though 30 seconds is not
an integer number of 512-frame windows. The result uses `MAX_DURATION`; remaining real samples are
retained in order for subsequent segmentation. Stream finalization completes confirmed speech with
`STREAM_ENDED` and discards an unconfirmed candidate explicitly.

Events are returned directly in deterministic order: `SPEECH_STARTED`, `SPEECH_ENDED`,
`UTTERANCE_COMPLETED`, and `UTTERANCE_DISCARDED`. They use absolute frames as the primary timeline;
seconds are derived by division by 16,000. The acoustic speech end and later confirmation time are
not represented as the same moment.

## Configuration

VAD is disabled by default. Enabling VAD does not authorize microphone capture; a diagnostic
`listen` also requires `KOSMOS_VOICE_ENABLED=true`.

| Variable | Default |
| --- | --- |
| `KOSMOS_VAD_ENABLED` | `false` |
| `KOSMOS_VAD_BACKEND` | `silero` |
| `KOSMOS_VAD_MODEL_PATH` | unset |
| `KOSMOS_VAD_MODEL_REVISION` | pinned commit above |
| `KOSMOS_VAD_MODEL_SHA256` | unset |
| `KOSMOS_VAD_SPEECH_THRESHOLD` | `0.5` |
| `KOSMOS_VAD_END_SPEECH_THRESHOLD` | `0.35` |
| `KOSMOS_VAD_MIN_SPEECH_MS` | `160` |
| `KOSMOS_VAD_MIN_SILENCE_MS` | `640` |
| `KOSMOS_VAD_PRE_ROLL_MS` | `256` |
| `KOSMOS_VAD_POST_ROLL_MS` | `128` |
| `KOSMOS_VAD_MAX_UTTERANCE_SECONDS` | `30` |

Settings reject booleans used as numbers, non-finite values, invalid threshold ordering, excessive
durations, non-absolute or non-regular paths, non-ONNX extensions, empty or over-32-MiB models, and
configured checksum mismatches. A checksum verifies bytes, not origin, consent, or safety.

## Manual installation and diagnostics

Install dependencies without a model:

```bash
uv sync --frozen --dev --extra vad
uv run --no-sync kosmos-vad status
```

After explicit authorization, obtain the file from the immutable upstream revision. These examples
are documentation only; Kosmos never runs them automatically.

Windows CMD:

```bat
mkdir "%LOCALAPPDATA%\Kosmos\vad\models"
curl.exe -L "https://raw.githubusercontent.com/snakers4/silero-vad/5cd7945676eb32225748052e2e6a0580e4686a08/src/silero_vad/data/silero_vad.onnx" -o "%LOCALAPPDATA%\Kosmos\vad\models\silero-vad-v6.2.3.onnx"
certutil -hashfile "%LOCALAPPDATA%\Kosmos\vad\models\silero-vad-v6.2.3.onnx" SHA256
set KOSMOS_VAD_MODEL_PATH=%LOCALAPPDATA%\Kosmos\vad\models\silero-vad-v6.2.3.onnx
set KOSMOS_VAD_MODEL_SHA256=1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3
set KOSMOS_VAD_ENABLED=true
```

Ubuntu:

```bash
mkdir -p "$HOME/.local/share/kosmos/vad/models"
curl -L 'https://raw.githubusercontent.com/snakers4/silero-vad/5cd7945676eb32225748052e2e6a0580e4686a08/src/silero_vad/data/silero_vad.onnx' -o "$HOME/.local/share/kosmos/vad/models/silero-vad-v6.2.3.onnx"
sha256sum "$HOME/.local/share/kosmos/vad/models/silero-vad-v6.2.3.onnx"
export KOSMOS_VAD_MODEL_PATH="$HOME/.local/share/kosmos/vad/models/silero-vad-v6.2.3.onnx"
export KOSMOS_VAD_MODEL_SHA256=1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3
export KOSMOS_VAD_ENABLED=true
```

Compare the exact hash and byte size before use, record the source revision, disconnect networking,
then run `status` followed by an explicit reviewed WAV. Physical capture is a later, separate step.

```bash
uv run --no-sync kosmos-vad --help
uv run --no-sync kosmos-vad status
uv run --no-sync kosmos-vad analyze --file sample.wav
uv run --no-sync kosmos-vad listen --duration 5
```

`status` imports optional packages to report availability but does not read the model, create a
session, infer, or open a device. `analyze` accepts only a local uncompressed compatible WAV up to
five minutes. `listen` validates and loads the model before announcing and opening a device for at
most 30 seconds, then labels processing as occurring after capture. No command transcribes, plays,
persists, uploads, or grants authority from detected activity.

## Metrics, privacy, and pending validation

Detector metrics contain backend, revision, device, sample rate, frame size, real frames processed,
inference count, measured load time, measured inference time, and inference RTF. CLI processing RTF
includes framing and segmentation. No PCM or probability history is logged or persisted. Python and
the native runtime can retain temporary memory; Kosmos does not claim cryptographic erasure.

Expected simulated output shapes include `Speech started: 0.512s`, `Speech ended: 1.536s`,
`Utterance completed: 2.048s`, `End reason: silence`, `End reason: max_duration`, and controlled
errors for a missing model, checksum mismatch, unavailable backend, incompatible PCM, or invalid
probability. These examples are not real detection evidence.

Stage 02.8 must validate onset and offset clipping, short commands, natural pauses, continuous
speech, silence, environmental and keyboard noise, background speech, playback, false-positive and
false-negative rates, endpoint latency, RTF, CPU, memory, and utterance durations. Real VAD,
physical microphone, Windows/Ubuntu offline behavior, performance, thresholds, and Brazilian
Portuguese calibration remain pending. Stage 02.5 is not implemented by this work.
