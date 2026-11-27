"""Explicit development diagnostics for local speech recognition."""

import argparse
import asyncio
import re
import sys
import wave
from collections.abc import Sequence
from pathlib import Path

from kosmos.voice.audio.adapters.sounddevice import SoundDeviceCapture
from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.config import load_voice_settings
from kosmos.voice.exceptions import SpeechRecognitionError, VoiceError
from kosmos.voice.stt.adapters.faster_whisper import FasterWhisperRecognizer
from kosmos.voice.stt.config import STTSettings, load_stt_settings
from kosmos.voice.stt.models import SpeechRecognitionRequest, SpeechRecognitionResult

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kosmos-stt",
        description="Inspect and explicitly exercise local speech recognition.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="inspect configuration without loading a model")
    subparsers.add_parser("models", help="show the explicitly configured local model")
    transcribe = subparsers.add_parser("transcribe", help="transcribe a compatible local WAV")
    transcribe.add_argument("--file", required=True, type=Path)
    listen = subparsers.add_parser("listen", help="explicitly capture and transcribe bounded audio")
    listen.add_argument("--device", type=int)
    listen.add_argument("--duration", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(run_command(arguments, settings=load_stt_settings()))
    except KeyboardInterrupt:
        print(
            "STT diagnostic interrupted; native work may finish before resources are released.",
            file=sys.stderr,
        )
        return EXIT_INTERRUPTED
    except VoiceError as error:
        print(f"Error: {_sanitize(str(error))}", file=sys.stderr)
        return EXIT_ERROR


async def run_command(arguments: argparse.Namespace, *, settings: STTSettings) -> int:
    if arguments.command == "status":
        _print_status(settings)
        return EXIT_OK
    if arguments.command == "models":
        model = settings.validate_model()
        print(f"{model.identifier} | revision={model.revision} | path={model.path}")
        return EXIT_OK

    recognizer = FasterWhisperRecognizer(settings)
    try:
        if arguments.command == "transcribe":
            chunk = _read_wav(arguments.file, settings.max_audio_seconds)
        elif arguments.command == "listen":
            voice = load_voice_settings()
            if arguments.duration <= 0 or arguments.duration > settings.max_audio_seconds:
                raise SpeechRecognitionError("Capture duration is outside the STT limit")
            await recognizer.load()
            print(
                f"Opening the microphone for {arguments.duration:g} seconds; "
                "audio remains in memory only."
            )
            capture = SoundDeviceCapture(
                voice_enabled=voice.enabled,
                duration_limit_seconds=settings.max_audio_seconds,
            )
            try:
                chunk = await asyncio.to_thread(
                    capture.capture,
                    duration_seconds=arguments.duration,
                    audio_format=AudioFormat(16_000, 1),
                    device=arguments.device if arguments.device is not None else voice.input_device,
                    block_size=voice.block_size,
                )
            finally:
                capture.close()
        else:
            raise AssertionError("argparse accepted an unknown STT command")

        result = await recognizer.recognize(SpeechRecognitionRequest(chunk))
        _print_result(result)
        return EXIT_OK
    finally:
        await recognizer.close()


def _print_status(settings: STTSettings) -> None:
    try:
        settings.validate_model()
        model_available = True
        configuration_valid = True
    except SpeechRecognitionError:
        model_available = bool(settings.model_path and settings.model_path.is_dir())
        configuration_valid = False

    try:
        from kosmos.voice.stt.adapters.faster_whisper import load_faster_whisper_backend

        load_faster_whisper_backend()
        dependencies_available = True
    except SpeechRecognitionError:
        dependencies_available = False

    print(f"STT enabled: {_yes_no(settings.enabled)}")
    print(f"Backend: {settings.backend}")
    print(f"Optional dependencies available: {_yes_no(dependencies_available)}")
    print(f"Local model files available: {_yes_no(model_available)}")
    print(f"Model identifier: {settings.model_identifier}")
    print(f"Language: {settings.language}")
    print(f"Execution: {settings.device}/{settings.compute_type}")
    print(f"CPU threads: {settings.cpu_threads}")
    print(f"Maximum audio duration: {settings.max_audio_seconds:g} seconds")
    print(f"Model configuration valid: {_yes_no(configuration_valid)}")
    print("Real recognition verified: no")


def _read_wav(path: Path, max_seconds: float) -> AudioChunk:
    if not path.is_file():
        raise SpeechRecognitionError("Configured WAV file is unavailable")
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise SpeechRecognitionError("STT accepts only uncompressed PCM WAV files")
            compatible = (
                source.getframerate() == 16_000
                and source.getnchannels() == 1
                and source.getsampwidth() == 2
            )
            if not compatible:
                raise SpeechRecognitionError("STT requires mono 16000 Hz 16-bit PCM WAV")
            frames = source.getnframes()
            if frames <= 0 or frames > round(16_000 * max_seconds):
                raise SpeechRecognitionError("WAV duration is empty or exceeds the STT limit")
            data = source.readframes(frames)
    except (wave.Error, EOFError, OSError) as error:
        raise SpeechRecognitionError("WAV file could not be read safely") from error

    return AudioChunk(data, AudioFormat(16_000, 1))


def _print_result(result: SpeechRecognitionResult) -> None:
    print(f"Status: {result.status.value}")
    print(f"Transcript: {_sanitize(result.text) if result.text else '(none)'}")
    for segment in result.segments:
        print(
            f"[{segment.start_seconds:.3f}s -> {segment.end_seconds:.3f}s] "
            f"{_sanitize(segment.text)}"
        )
    metrics = result.metrics
    print(
        f"Recognition: {metrics.recognition_seconds:.3f}s; load: "
        f"{metrics.model_loading_seconds:.3f}s; RTF: {metrics.real_time_factor:.3f}; "
        f"segments: {metrics.segment_count}."
    )


def _sanitize(value: str) -> str:
    return _CONTROL_CHARACTERS.sub("", value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
