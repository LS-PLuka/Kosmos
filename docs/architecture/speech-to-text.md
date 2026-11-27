# Speech-to-Text

Stage 02.3 adds bounded local speech recognition without connecting transcription to the Core
Engine, Qwen, TTS, or automatic tool execution. Automated tests use fake models and synthetic PCM.
Real recognition, microphone, offline, performance, and model-quality validation remain pending.

## Architecture and contracts

The dependency flow is `AudioChunk -> SpeechRecognizer -> Faster Whisper adapter -> immutable
SpeechRecognitionResult`. Capture remains an explicit, separate `AudioCapture` operation. Public
STT contracts contain no Faster Whisper, CTranslate2, NumPy, PyAV, SoundDevice, Piper, Ollama, or
Qwen types.

Input is mono 16 kHz signed 16-bit little-endian PCM. Requests are limited to 30 seconds (960,000
bytes), validated before conversion, and never resampled, downmixed, persisted, replayed, or sent
over a network. NumPy conversion occurs only inside the adapter and normalizes `int16` samples to
`float32` by division by 32768.0.

`TRANSCRIBED` requires text and ordered temporal segments. `NO_TRANSCRIPTION` is a normal complete
outcome for an empty backend result; it does not prove acoustic silence. Empty PCM and all-zero PCM
are rejected deterministically. VAD, energy analysis, silence segmentation, diarization, word
timestamps, and arbitrary rejection of short phrases are intentionally absent.

## Faster Whisper adapter

The reviewed library release is Faster Whisper 1.2.1 (MIT, Python 3.9 or later). The resolved
runtime is CTranslate2 4.9.1, which provides CPython 3.12 wheels for Windows x86-64 and Linux
x86-64. Execution is fixed to CPU, INT8 compute, four configurable CPU threads, one worker,
Portuguese (`pt`), transcription, beam size one, no translation, `vad_filter=False`, and
`condition_on_previous_text=False`. These defaults have no local performance or quality claim.

The model is loaded lazily and reused by one recognizer instance. The adapter accepts only an
absolute existing directory and requires `config.json`, `model.bin`, `tokenizer.json`, and
`vocabulary.txt` before constructing `WhisperModel`. It passes the validated directory and
`local_files_only=True`. Requiring the local tokenizer prevents the backend path that can consult
the Hugging Face Hub for tokenizer data. Kosmos never passes a remote identifier to the backend,
downloads a model, or changes global networking settings. Actual air-gapped execution still
requires manual validation on the target Ubuntu host.

Faster Whisper returns a lazy iterable. The adapter consumes it completely inside its boundary,
validates every segment, and includes iteration in recognition duration. A generator failure fails
the whole request; no partial transcript is published or persisted.

## Lifecycle, concurrency, cancellation, and metrics

One native operation is allowed per recognizer. A second request fails with a controlled busy
error. `load()` is explicit, while `recognize()` may perform the same lazy load. `close()` rejects
use while native work is active and prevents later requests after completion.

Blocking inference runs through `asyncio.to_thread()`. Cancelling the waiting coroutine propagates
cancellation to the consumer but cannot stop CTranslate2's native thread. The operation remains
reserved until the real thread completes, and its result is not returned to the cancelled caller.
No hard timeout is exposed because the backend does not provide a safe interrupt guarantee.

Metrics contain backend, model identifier, device, compute type, configured language, input
duration/frames/bytes, measured load/recognition/total durations, segment and character counts,
model reuse, and real-time factor. They contain no PCM, transcript, WER, CER, or invented confidence.

## Optional installation and local model

```bash
uv sync --frozen --dev
uv sync --frozen --dev --extra voice
uv sync --frozen --dev --extra voice --extra stt
```

The reference model is the multilingual `Systran/faster-whisper-base` repository at revision
`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`. It is approximately 148 MB and declares MIT. Its
stored weights are FP16; INT8 describes runtime compute, not the stored file. The repository
publishes SHA-256 `d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9` for
`model.bin`. Calculate and record hashes for every downloaded file.

Model acquisition is a separate, explicit network operation and is never performed by Kosmos.
After installing the `stt` extra, an authorized maintainer can run:

Windows CMD:

```bat
uv run --no-sync hf download Systran/faster-whisper-base --revision ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 --local-dir "%LOCALAPPDATA%\Kosmos\stt\models\base"
certutil -hashfile "%LOCALAPPDATA%\Kosmos\stt\models\base\model.bin" SHA256
set KOSMOS_STT_MODEL_PATH=%LOCALAPPDATA%\Kosmos\stt\models\base
set KOSMOS_STT_ENABLED=true
```

Ubuntu:

```bash
uv run --no-sync hf download Systran/faster-whisper-base --revision ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 --local-dir "$HOME/.local/share/kosmos/stt/models/base"
sha256sum "$HOME/.local/share/kosmos/stt/models/base/model.bin"
export KOSMOS_STT_MODEL_PATH="$HOME/.local/share/kosmos/stt/models/base"
export KOSMOS_STT_ENABLED=true
```

Inspect the four required files, compare the published model hash, record the exact revision and
locally calculated hashes, then disconnect networking for explicit offline validation. Tiny and
Small multilingual converted models may be configured by path; Kosmos does not discover, switch,
or load multiple models automatically.

## Configuration and diagnostics

| Variable | Default | Purpose |
| --- | --- | --- |
| `KOSMOS_STT_ENABLED` | `false` | explicit recognition gate |
| `KOSMOS_STT_BACKEND` | `faster-whisper` | fixed local adapter |
| `KOSMOS_STT_MODEL_PATH` | unset | absolute validated model directory |
| `KOSMOS_STT_MODEL_IDENTIFIER` | `Systran/faster-whisper-base` | audit identity |
| `KOSMOS_STT_MODEL_REVISION` | pinned revision above | audit revision |
| `KOSMOS_STT_LANGUAGE` | `pt` | Whisper language code |
| `KOSMOS_STT_CPU_THREADS` | `4` | bounded CTranslate2 CPU threads |
| `KOSMOS_STT_BEAM_SIZE` | `1` | bounded decoding beam |
| `KOSMOS_STT_MAX_AUDIO_SECONDS` | `30` | request and capture limit |

Loading configuration has no model, device, file, network, or inference side effect. Enabling STT
does not authorize microphone access; `KOSMOS_VOICE_ENABLED=true` is independently required.

```bash
uv run --no-sync kosmos-stt --help
uv run --no-sync kosmos-stt status
uv run --no-sync kosmos-stt models
uv run --no-sync kosmos-stt transcribe --file sample.wav
uv run --no-sync kosmos-stt listen --duration 5
uv run --no-sync kosmos-stt listen --device 1 --duration 5
```

`status` never loads a model or opens a device. `models` reports only the configured validated
directory. `transcribe` accepts only an explicit compatible local PCM WAV. `listen` validates and
loads the model before clearly announcing and opening a microphone for a finite duration. Terminal
control characters are removed from backend text before display.

## Security, licensing, and pending validation

Audio and transcripts remain local and in memory, are not logged or persisted automatically, and
never grant authority. A transcript is untrusted input, not a system instruction. There is no
telemetry, external fallback, cloud API, passive listening, startup inference, biometric identity,
or automatic Core/TTS/tool integration.

The `stt` extra directly contains Faster Whisper and NumPy. The lockfile resolves CTranslate2,
PyAV (with bundled FFmpeg libraries), Hugging Face Hub, Tokenizers, ONNX Runtime, tqdm, PyYAML,
protobuf, flatbuffers, and support packages. Exact notices and the native-code distribution
boundary require review before redistribution. Automated simulation does not validate Brazilian
Portuguese accuracy, false transcription under silence/noise, model quality, latency, memory,
physical microphones, Windows/Ubuntu runtime behavior, or offline guarantees.

Manual evaluation should cover short commands, questions, Java/Spring, Docker, arithmetic,
AWS/Kubernetes/GitHub Actions/CTranslate2, corrections, "Pare", "Sim", "Não", and mixed
Portuguese/English. These phrases are transcription input only and must never execute actions.
