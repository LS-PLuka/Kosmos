# Text-to-Speech

Stage 02.2 adds bounded local speech synthesis without connecting it to the Core Engine or
conversation CLI. Automated tests use simulated processes and audio devices. Real Piper synthesis,
physical playback, voice quality, and Ubuntu validation remain pending maintainer actions.

## Architecture and public contracts

The dependency flow is `text preparation -> SpeechSynthesizer -> external Piper process ->
AudioChunk`. Playback is a separate explicit call through the Stage 02.1 `AudioPlayback` port.
`SpeechSynthesizer`, `SpeechSynthesisRequest`, `SpeechSynthesisResult`,
`SpeechSynthesisMetrics`, `SpeechVoice`, and `SpeechSynthesisSettings` contain no Piper,
SoundDevice, PortAudio, Ollama, Qwen, or CLI types.

Synthesis is asynchronous because it owns an external process. The Piper adapter starts one process
per request, so its measured process duration includes process startup and model loading. It does
not claim a persistent loaded model, streaming playback, time to first audible output, or internal
Piper inference time. Callers must await `close()`. Playback remains blocking and future async
consumers must run it outside the event loop; cancelling `asyncio.to_thread()` alone does not stop a
native audio operation.

## Piper external process adapter

The selected and reviewed release is Piper 1.8.0. It requires Python 3.9 or later and publishes
ABI3 wheels for Windows x86-64 and Linux x86-64/aarch64. Piper is installed separately and invoked
through its documented CLI with structured arguments:

```text
piper --model MODEL --config CONFIG --output-raw --length-scale SCALE --volume VOLUME
```

Prepared UTF-8 text is sent through stdin. `--output-raw` returns mono signed 16-bit PCM in the
voice model's sample rate. Kosmos determines that rate from the validated JSON configuration rather
than assuming capture's 16 kHz format. The adapter uses `asyncio.create_subprocess_exec`, which does
not invoke a shell. It rejects `.bat` and `.cmd` launchers, captures stdout and stderr concurrently,
applies limits while reading, enforces a total timeout, kills and awaits active processes after a
timeout or cancellation, and never exposes stderr content in expected errors.

The configured executable remains an external trust boundary. Install it from verified upstream
sources and protect its directory from untrusted modification. Text cannot select the executable,
paths, or command options. Raw Piper phoneme delimiters (`[[` and `]]`) are neutralized before input.

## Razo voice review

The provisional voice is `Lucasllfs/Razo-piper-voice`. The repository currently contains
`pt-BR-razo-medium.onnx` and `config.json`. Its card and config declare Brazilian Portuguese, one
male speaker, VITS/Piper ONNX, CPU execution, and a fixed 22,050 Hz sample rate. The remote ONNX
page publishes SHA-256
`91c815ae67edd7fbdd37925e3639a6c3dc5f57e58034223caac2a5ec5ecf548f`; this is a supplier-published
hash, not a hash calculated by Kosmos. The config page does not publish a comparable SHA-256.

The repository labels the model MIT and contains a license file, but the card only identifies the
dataset as `pt-br-faber-finetuning` and describes the model as a fine-tune. It does not provide a
complete dataset source, recording license, base-model chain, speaker consent, or voice-rights
record. Piper's own licensing guidance states that an engine license does not grant rights over a
voice and that fine-tune ancestry must be reviewed. Therefore Razo remains a provisional local
evaluation asset and must not be redistributed with Kosmos until legal, provenance, and rights
review is complete. Voice quality approval is also pending manual evaluation.

The adapter accepts the original `config.json` through an explicit path, so renaming it to
`pt-BR-razo-medium.onnx.json` is unnecessary. It validates the fields required to interpret Piper
output: `audio.sample_rate`, `espeak.voice`, `num_speakers`, and `phoneme_id_map`. Optional configured
SHA-256 values are checked before use. A local checksum proves file identity only; it does not prove
origin, license, consent, or safety.

## Independent installation

Do not install Piper in the Kosmos environment. The following commands create a separate runtime.
They do not install a model.

Windows CMD:

```bat
py -3.12 -m venv "%LOCALAPPDATA%\Kosmos\tts\piper-venv"
"%LOCALAPPDATA%\Kosmos\tts\piper-venv\Scripts\python.exe" -m pip install "piper-tts==1.8.0"
"%LOCALAPPDATA%\Kosmos\tts\piper-venv\Scripts\piper.exe" --help
```

Ubuntu:

```bash
python3 -m venv "$HOME/.local/share/kosmos/tts/piper-venv"
"$HOME/.local/share/kosmos/tts/piper-venv/bin/python" -m pip install 'piper-tts==1.8.0'
"$HOME/.local/share/kosmos/tts/piper-venv/bin/piper" --help
```

If `venv` or other operating-system packages are unavailable, install them manually according to
the operating-system documentation. Kosmos performs no administrative installation.

Download the two Razo files manually from the reviewed Hugging Face repository into a local user
data directory. Do not place them in the repository. Retain the upstream names and repository
revision in a local installation record. Verify the supplier-published model hash and calculate the
config hash after download.

Windows CMD example:

```bat
certutil -hashfile "%LOCALAPPDATA%\Kosmos\tts\voices\razo\pt-BR-razo-medium.onnx" SHA256
certutil -hashfile "%LOCALAPPDATA%\Kosmos\tts\voices\razo\config.json" SHA256
```

Ubuntu example:

```bash
sha256sum "$HOME/.local/share/kosmos/tts/voices/razo/pt-BR-razo-medium.onnx"
sha256sum "$HOME/.local/share/kosmos/tts/voices/razo/config.json"
```

Compare the ONNX result to the published hash above. Record the config result as locally calculated
because no supplier hash was identified during this review.

## Configuration

TTS is disabled by default. Loading settings does not read files, start processes, open devices,
download data, or access the network.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KOSMOS_TTS_ENABLED` | `false` | Explicit synthesis gate |
| `KOSMOS_TTS_BACKEND` | `piper` | Explicit backend selection |
| `KOSMOS_TTS_PIPER_EXECUTABLE` | unset | Trusted external executable path |
| `KOSMOS_TTS_MODEL_PATH` | unset | External ONNX path |
| `KOSMOS_TTS_CONFIG_PATH` | unset | External Piper JSON path |
| `KOSMOS_TTS_VOICE` | `razo` | Configured voice identifier |
| `KOSMOS_TTS_LENGTH_SCALE` | `1.0` | Phoneme duration; lower is faster |
| `KOSMOS_TTS_VOLUME` | `1.0` | Output sample multiplier |
| `KOSMOS_TTS_TIMEOUT_SECONDS` | `60` | Total external-process deadline |
| `KOSMOS_TTS_MODEL_SHA256` | unset | Optional expected model hash |
| `KOSMOS_TTS_CONFIG_SHA256` | unset | Optional expected config hash |

Length scale accepts 0.1 through 10.0, matching Piper's exposed UI range; 0.5 is approximately twice
as fast and 2.0 twice as slow. Volume accepts 0 through 10. Timeout accepts 0.1 through 300 seconds.
The adapter always uses CPU and never passes `--cuda`. Enabling TTS does not authorize microphone
capture and does not alter `KOSMOS_VOICE_ENABLED`.

Windows CMD example:

```bat
set KOSMOS_TTS_ENABLED=true
set KOSMOS_TTS_PIPER_EXECUTABLE=%LOCALAPPDATA%\Kosmos\tts\piper-venv\Scripts\piper.exe
set KOSMOS_TTS_MODEL_PATH=%LOCALAPPDATA%\Kosmos\tts\voices\razo\pt-BR-razo-medium.onnx
set KOSMOS_TTS_CONFIG_PATH=%LOCALAPPDATA%\Kosmos\tts\voices\razo\config.json
set KOSMOS_TTS_MODEL_SHA256=91c815ae67edd7fbdd37925e3639a6c3dc5f57e58034223caac2a5ec5ecf548f
```

Ubuntu uses the equivalent exported paths under `$HOME/.local/share/kosmos/tts`.

## Text, limits, metrics, and failures

Preparation removes decorative headings, list markers, emphasis, inline-code delimiters, and link
destinations while retaining visible labels and code contents. Fenced code is introduced as a code
block instead of discarded. Control characters are removed, whitespace is normalized, numbers,
units, signs, percentages, names, commands, and warnings are otherwise preserved. No LLM or NLP
dependency is involved.

Requests are limited to 8,000 input characters and split at sentences or whitespace into segments
of at most 1,000 characters. Segments are sent as lines to one process, preserving order. PCM and
the Stage 02.1 chunk are limited to 64 MiB, stderr to 64 KiB, and the default total timeout to 60
seconds. Oversized words and outputs fail explicitly; text is never silently truncated.

Metrics contain backend, voice identifier, character count, process duration, audio duration,
sample rate, frames, bytes, and real-time factor. They contain no text or PCM. Expected failures
distinguish disabled or unavailable backends, missing models, invalid configuration or requests,
timeouts, failed processes, invalid audio, and playback errors without returning raw stderr.

## Diagnostics and validation

`kosmos-tts` is separate from `kosmos-audio` because synthesis has its own backend, configuration,
and lifecycle while reusing only the playback port.

```bash
uv run --no-sync kosmos-tts --help
uv run --no-sync kosmos-tts status
uv run --no-sync kosmos-tts voices
uv run --no-sync kosmos-tts synthesize --text "Olá, senhor."
uv run --no-sync kosmos-tts speak --text "À sua disposição, senhor."
```

`status` and `voices` never synthesize or open audio devices. `synthesize` retains PCM in memory and
does not play or persist it. `speak` is the only command that explicitly requests playback.

Manual voice evaluation phrases:

- "Sou Kosmos, seu assistente pessoal. Estou aqui para facilitar as coisas."
- "Bom dia, senhor. Como posso ajudá-lo?"
- "Claro, senhor. À sua disposição."
- "O Docker permite empacotar aplicações e suas dependências em containers."
- "Java, Spring Boot, PostgreSQL, RabbitMQ, Kubernetes e Amazon Web Services."
- "O resultado da operação é 4.000."
- "Ainda não tenho informações suficientes para confirmar essa hipótese."
- "Atenção, senhor. Recomendo interromper essa operação imediatamente."
- "Funcionou de primeira. Um acontecimento relativamente raro na engenharia de software."
- "Até mais, senhor. Estarei por aqui."

Evaluate naturalness, pronunciation, Brazilian accent, clarity, pace, timbre, pauses, technical
terms, numbers, and identity. Do not treat these phrases as Qwen output. No real synthesis or
physical playback is part of automated validation.

## Licensing and distribution boundary

Piper 1.8.0 is GPL-3.0-or-later. Kosmos imports no Piper code and distributes no Piper package,
binary, voice, or model. The external-process boundary is intended to preserve technical and
distribution separation, but it is not an automatic legal compatibility guarantee. Review is
required before any joint distribution. Kosmos remains PolyForm Noncommercial 1.0.0 and
source-available.

Known limitations include process and model startup latency per request, no resampling, no
persistent daemon, no real-time playback, no synthesis cache, no voice download manager, no STT,
VAD, wake word, voice orchestration, or benchmark. An output device that cannot play 22,050 Hz must
fail explicitly; adaptation belongs to a later approved stage.
