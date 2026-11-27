# Audio and TTS Validation

These checks are explicit physical diagnostics for Stage 02.1. Automated tests never open an audio
device. Review the selected device before enabling capture; installation of the `voice` extra is not
consent to use a microphone.

Stage 02.2 TTS automated tests use a simulated Piper process. Follow the independent installation,
configuration, hash, provenance, and licensing review in the
[Text-to-Speech specification](../architecture/text-to-speech.md) before real synthesis.

Stage 02.3 STT automated tests use fake models and synthetic PCM. Follow the manual model
installation, pinned revision, hash, offline, and privacy procedure in the
[Speech-to-Text specification](../architecture/speech-to-text.md) before real recognition.

## Install and inspect

```bash
uv sync --frozen --dev --extra voice
uv run --no-sync kosmos-audio --help
uv run --no-sync kosmos-audio devices
uv run --no-sync kosmos-audio status
```

`devices` and `status` enumerate metadata but do not open input or output streams. Device indices
are local to the current PortAudio enumeration and can change after a restart or hardware change.

On Windows, the SoundDevice wheel supplies PortAudio. On Ubuntu, install the distribution's runtime
PortAudio package manually if it is absent (commonly `libportaudio2`), then repeat `status`. Kosmos
does not execute administrative package installation.

## Windows CMD capture and playback

```bat
set KOSMOS_VOICE_ENABLED=true
uv run --no-sync kosmos-audio test-input --duration 3
uv run --no-sync kosmos-audio test-input --device 1 --duration 3 --playback
uv run --no-sync kosmos-audio test-output --device 3
set KOSMOS_VOICE_ENABLED=
```

## Ubuntu capture and playback

```bash
KOSMOS_VOICE_ENABLED=true uv run --no-sync kosmos-audio test-input --duration 3
KOSMOS_VOICE_ENABLED=true uv run --no-sync kosmos-audio test-input \
  --device 1 --duration 3 --playback
uv run --no-sync kosmos-audio test-output --device 3
```

Input defaults to mono signed 16-bit PCM at 16 kHz. `test-output` generates a 250 ms, 440 Hz mono
tone at 48 kHz and conservative amplitude unless `--sample-rate` is explicitly supplied. Playback
after capture occurs only after the microphone stream closes and retains PCM in memory only.

## Expected simulated examples

The following examples illustrate output shape only; they come from fake devices and are not proof
of physical compatibility:

```text
[0] Fake Microphone | input | host=Fake Host | in=2 | out=0 | default-rate=48000 Hz; default input
Voice enabled: no
Starting explicit microphone capture for 3 seconds; audio will remain in memory only.
Capture complete: 48000 frames, 96000 bytes, 3.000 seconds.
Playback complete.
Error: Audio device 9 was not found
Error: Voice support is not installed; install the 'voice' extra
Error: Input device does not support the requested PCM format
```

## Manual acceptance record

Record operating system, Python and SoundDevice versions, host API, selected devices, requested
formats, success or failure, and any overflow, underflow, permission, disconnect, or latency
observation. Do not commit recordings, device-private information, or raw PCM. Windows and Ubuntu
physical validation remain pending until the maintainer performs and records these checks.

For TTS, first run `kosmos-tts status` and `kosmos-tts voices`. Then run `synthesize` without
playback and record Piper version, model repository revision, locally calculated hashes, sample
rate, process duration, audio duration, bytes, frames, and real-time factor. Only then run `speak`
with a reviewed output device. Record pronunciation and voice-quality findings separately. Do not
commit generated audio, model weights, local paths, or raw diagnostic output containing private
device data. Real Windows and Ubuntu synthesis, physical playback, and Razo voice-quality
validation remain pending.

For STT, run `kosmos-stt status` and `kosmos-stt models` before enabling recognition. First use an
explicit reviewed WAV with `kosmos-stt transcribe --file sample.wav`; only then enable voice capture
and use `kosmos-stt listen --duration 5`. Record package and model revisions, local hashes,
language, threads, durations, RTF, segment observations, false transcriptions, and errors. Do not
commit recordings, transcripts, model files, device-private information, or local paths. Real
recognition, physical microphone, offline, performance, and model-selection validation remain
pending on Windows and Ubuntu.
