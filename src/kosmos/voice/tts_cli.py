"""Explicit development diagnostics for local text-to-speech."""

import argparse
import asyncio
import shutil
import sys
from collections.abc import Sequence

from kosmos.voice.audio.adapters.sounddevice import SoundDevicePlayback
from kosmos.voice.config import load_voice_settings
from kosmos.voice.exceptions import SpeechSynthesisError, VoiceError
from kosmos.voice.tts.adapters.piper import PiperExternalProcessSynthesizer
from kosmos.voice.tts.config import TTSSettings, load_tts_settings
from kosmos.voice.tts.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    SpeechSynthesisSettings,
    SpeechVoice,
)
from kosmos.voice.tts.playback import play_synthesis
from kosmos.voice.tts.text import prepare_text

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kosmos-tts",
        description="Inspect and explicitly exercise local text-to-speech.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="inspect configuration without running synthesis")
    subparsers.add_parser("voices", help="list configured and locally available voices")
    for command, help_text in (
        ("synthesize", "synthesize PCM in memory without playback"),
        ("speak", "synthesize and explicitly play PCM"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("--text", required=True, help="bounded text to synthesize")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(run_command(arguments, settings=load_tts_settings()))
    except KeyboardInterrupt:
        print("TTS diagnostic interrupted; active resources were closed.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except VoiceError as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_ERROR


async def run_command(arguments: argparse.Namespace, *, settings: TTSSettings) -> int:
    if arguments.command == "status":
        _print_status(settings)
        return EXIT_OK
    if arguments.command == "voices":
        _print_voices(settings)
        return EXIT_OK
    if arguments.command in {"synthesize", "speak"}:
        result = await _synthesize(arguments.text, settings)
        if arguments.command == "speak":
            voice_settings = load_voice_settings()
            playback = SoundDevicePlayback()
            try:
                play_synthesis(result, playback, device=voice_settings.output_device)
            finally:
                playback.close()
            print("Playback complete.")
        _print_metrics(result)
        return EXIT_OK

    raise AssertionError("argparse accepted an unknown TTS command")


def _print_status(settings: TTSSettings) -> None:
    executable_available = False
    if settings.executable is not None:
        executable_available = settings.executable.suffix.lower() not in {".bat", ".cmd"} and (
            shutil.which(str(settings.executable)) is not None or settings.executable.is_file()
        )
    try:
        metadata = settings.load_voice_metadata()
        model_available = True
        configuration_valid = True
    except SpeechSynthesisError:
        metadata = None
        model_available = bool(settings.model_path and settings.model_path.is_file())
        configuration_valid = False

    print(f"TTS enabled: {_yes_no(settings.enabled)}")
    print(f"Backend: {settings.backend}")
    print(f"Backend executable available: {_yes_no(executable_available)}")
    print(f"Voice model available: {_yes_no(model_available)}")
    print(f"Voice identifier: {settings.voice_identifier}")
    print(f"Language: {metadata.language if metadata and metadata.language else 'unknown'}")
    print(f"Configured sample rate: {metadata.audio_format.sample_rate if metadata else 'unknown'}")
    print("Execution device: CPU")
    print(f"Timeout: {settings.timeout_seconds:g} seconds")
    print(f"Voice configuration valid: {_yes_no(configuration_valid)}")
    print("Real synthesis verified: no")


def _print_voices(settings: TTSSettings) -> None:
    metadata = settings.load_voice_metadata()
    print(
        f"{settings.voice_identifier} | language={metadata.language or 'unknown'} | "
        f"sample-rate={metadata.audio_format.sample_rate} Hz | speakers={metadata.speaker_count}"
    )


async def _synthesize(text: str, settings: TTSSettings) -> SpeechSynthesisResult:
    prepared = prepare_text(text)
    request = SpeechSynthesisRequest(
        text=prepared,
        voice=SpeechVoice(settings.voice_identifier),
        settings=SpeechSynthesisSettings(settings.length_scale, settings.volume),
    )
    synthesizer = PiperExternalProcessSynthesizer(settings)
    try:
        return await synthesizer.synthesize(request)
    finally:
        await synthesizer.close()


def _print_metrics(result: SpeechSynthesisResult) -> None:
    metrics = result.metrics
    print("Synthesis complete in memory; no audio was persisted.")
    print(
        f"Audio: {metrics.audio_frames} frames, {metrics.audio_bytes} bytes, "
        f"{metrics.audio_duration_seconds:.3f} seconds at {metrics.sample_rate} Hz."
    )
    print(
        f"Process duration: {metrics.process_duration_seconds:.3f} seconds; "
        f"real-time factor: {metrics.real_time_factor:.3f}."
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
