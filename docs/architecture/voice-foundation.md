# Voice Foundation

Stage 02.1 establishes local PCM audio infrastructure without implementing speech synthesis,
recognition, voice activity detection, wake words, voice orchestration, or continuous interaction.
The feature branch is automatically validated; physical Windows and Ubuntu device validation and
Git integration remain pending.

## Responsibilities and dependency direction

The `kosmos.voice` package owns audio models, configuration, bounded buffering, device discovery,
capture, playback, and development diagnostics. The Core Engine does not import Voice Foundation.
Future voice orchestration may consume public Core contracts, but dependency direction must never
make Core depend on audio.

Domain models and ports do not expose SoundDevice, PortAudio, CFFI, NumPy, Ollama, Qwen, or any
presentation framework. `kosmos.voice.audio.adapters.sounddevice` is the only backend boundary. It
loads the optional dependency lazily when an explicit diagnostic or adapter operation requests it.
Importing Kosmos or Voice Foundation does not enumerate or open devices.

## Public contracts and models

`AudioFormat` describes interleaved PCM through sample rate, channel count, and `SampleFormat`.
Stage 02.1 supports signed 16-bit little-endian PCM. A sample is one channel value; a frame contains
one sample for every channel; bytes are storage; duration is `frames / sample_rate`.

`AudioChunk` contains immutable PCM bytes and rejects partial frames and payloads over 64 MiB.
`AudioDevice` exposes the process-local PortAudio index, name, host API, channel capabilities,
default sample rate, direction, and default flags. PortAudio indices may change between starts and
are not persistent identifiers.

The `AudioDeviceDiscovery`, `AudioCapture`, and `AudioPlayback` protocols are backend-independent.
`BoundedAudioBuffer` preserves order and complete frames, rejects incompatible formats, and raises
instead of silently dropping data when its configured capacity would be exceeded.

## SoundDevice adapter

`SoundDeviceDiscovery` uses `query_devices()`, `query_hostapis()`, `check_input_settings()`, and
`check_output_settings()`. An omitted device means the operating-system default; the adapter never
falls back to the first device when no default exists. It does not change system defaults.

`SoundDeviceCapture` uses a blocking `RawInputStream`, reads bounded blocks, detects reported input
overflow, returns one in-memory `AudioChunk`, and closes the stream after success or failure.
Capture requires both an explicit operation and `KOSMOS_VOICE_ENABLED=true`. The default diagnostic
duration is three seconds and the hard configured limit is 30 seconds.

`SoundDevicePlayback` uses a blocking `RawOutputStream`, reports underflow, closes resources after
success or failure, and offers explicit `stop()` through backend abort. `play()` returns false when
interrupted and does not claim completion. The diagnostic tone is generated locally at conservative
amplitude. Playback uses the content's declared sample rate; no resampling or silent conversion is
performed.

These operations are intentionally synchronous. AsyncIO consumers must run them outside the event
loop, for example with `asyncio.to_thread()`. No worker thread, callback inference, network work, or
generic streaming framework is introduced in Stage 02.1.

## Configuration

Voice configuration is immutable and read without side effects:

| Variable | Default | Consumer |
| --- | --- | --- |
| `KOSMOS_VOICE_ENABLED` | `false` | microphone authorization gate |
| `KOSMOS_VOICE_INPUT_DEVICE` | system default | capture selection |
| `KOSMOS_VOICE_OUTPUT_DEVICE` | system default | playback selection |
| `KOSMOS_VOICE_INPUT_SAMPLE_RATE` | `16000` | capture format |
| `KOSMOS_VOICE_INPUT_CHANNELS` | `1` | capture format |
| `KOSMOS_VOICE_BLOCK_SIZE` | `1024` | bounded capture reads |

Input defaults are mono signed 16-bit PCM at 16 kHz. Output configuration is derived from the PCM
content or explicit diagnostic sample rate and is not forced to 16 kHz.

## Optional dependency and installation

The `voice` extra pins SoundDevice to `>=0.5.6,<0.6`. SoundDevice 0.5.6 supports Python 3.12 and
Windows and Linux, is MIT licensed, and depends on CFFI and pycparser. Raw streams operate on Python
buffers, so NumPy is not required.

```bash
uv sync --frozen --dev --extra voice
```

The Windows wheel includes PortAudio. Ubuntu requires a compatible system PortAudio shared library,
commonly provided by the distribution package named `libportaudio2`; installation remains a manual
administrator action. A missing Python package and an unavailable native library produce distinct,
actionable backend errors. Conventional Core installation remains:

```bash
uv sync --frozen --dev
```

## Security, privacy, and lifecycle

- no capture starts during import, Core startup, textual CLI startup, status, or device listing;
- audio remains local and is never transmitted, transcribed, or persisted automatically;
- raw PCM is not logged, and diagnostics expose metadata only;
- captured PCM is held only for the requested operation and released normally afterward, without
  claiming cryptographic erasure from RAM;
- memory and duration limits are explicit, and overflow is never silently discarded;
- streams have one clear owner and are stopped and closed after success, failure, or interruption.

Errors distinguish optional dependency/native backend availability, invalid configuration, missing
or wrong-direction devices, unsupported formats, capture failure, playback failure, overflow, and
underflow while preserving the original exception as the internal cause.

## Validation and limitations

Automated tests inject a fake backend and require no audio hardware, PortAudio, GPU, Ollama, model,
credential, internet access, capture, or playback. See the
[audio validation guide](../development/audio-validation.md) for explicit physical checks.

Stage 02.1 does not provide codecs, compression, resampling, noise suppression, echo cancellation,
automatic gain control, mixer control, indefinite capture, disk recording, TTS, STT, VAD, wake
words, or real-time conversation. Physical compatibility, latency, permissions, disconnect behavior,
and device-specific formats remain pending on Windows and the target Ubuntu host.
