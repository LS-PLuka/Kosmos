# Audio Validation

These checks are explicit physical diagnostics for Stage 02.1. Automated tests never open an audio
device. Review the selected device before enabling capture; installation of the `voice` extra is not
consent to use a microphone.

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
