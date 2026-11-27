"""Explicit, development-only diagnostics for the local audio foundation."""

import argparse
import math
import struct
import sys
from collections.abc import Sequence
from importlib.util import find_spec

from kosmos.voice.audio.adapters.sounddevice import (
    SoundDeviceBackend,
    SoundDeviceCapture,
    SoundDeviceDiscovery,
    SoundDevicePlayback,
    load_sounddevice_backend,
)
from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.config import VoiceSettings, load_voice_settings
from kosmos.voice.exceptions import AudioBackendUnavailableError, VoiceError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130
DEFAULT_CAPTURE_SECONDS = 3.0
TEST_OUTPUT_SAMPLE_RATE = 48_000
TEST_TONE_SECONDS = 0.25
TEST_TONE_HERTZ = 440.0
TEST_TONE_AMPLITUDE = 0.15


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kosmos-audio",
        description="Inspect and explicitly test local PCM audio devices.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("devices", help="list local PortAudio devices without opening streams")
    subparsers.add_parser("status", help="show voice support and default-device status")

    input_parser = subparsers.add_parser("test-input", help="capture bounded PCM in memory")
    input_parser.add_argument("--device", type=int, help="explicit input device index")
    input_parser.add_argument(
        "--duration", type=float, default=DEFAULT_CAPTURE_SECONDS, help="seconds to capture"
    )
    input_parser.add_argument(
        "--playback", action="store_true", help="play captured PCM after capture completes"
    )

    output_parser = subparsers.add_parser("test-output", help="play a short local test tone")
    output_parser.add_argument("--device", type=int, help="explicit output device index")
    output_parser.add_argument(
        "--sample-rate", type=int, default=TEST_OUTPUT_SAMPLE_RATE, help="output sample rate"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        settings = load_voice_settings()
        try:
            backend = load_sounddevice_backend()
        except AudioBackendUnavailableError as error:
            if arguments.command == "status":
                _print_unavailable_status(settings, error)
                return EXIT_ERROR
            raise
        return run_command(arguments, settings=settings, backend=backend)
    except KeyboardInterrupt:
        print("Audio diagnostic interrupted; active resources were closed.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except VoiceError as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_ERROR


def run_command(
    arguments: argparse.Namespace,
    *,
    settings: VoiceSettings,
    backend: SoundDeviceBackend,
) -> int:
    discovery = SoundDeviceDiscovery(backend)
    if arguments.command == "devices":
        _print_devices(discovery)
        return EXIT_OK
    if arguments.command == "status":
        _print_status(settings, discovery)
        return EXIT_OK
    if arguments.command == "test-input":
        _test_input(arguments, settings, backend)
        return EXIT_OK
    if arguments.command == "test-output":
        _test_output(arguments, settings, backend)
        return EXIT_OK

    raise AssertionError("argparse accepted an unknown audio command")


def _print_devices(discovery: SoundDeviceDiscovery) -> None:
    devices = discovery.list_devices()
    if not devices:
        print("No audio devices are available.")
        return

    for device in devices:
        defaults = []
        if device.is_default_input:
            defaults.append("default input")
        if device.is_default_output:
            defaults.append("default output")
        suffix = f"; {', '.join(defaults)}" if defaults else ""
        print(
            f"[{device.index}] {device.name} | {device.direction.value} | "
            f"host={device.host_api} | in={device.max_input_channels} | "
            f"out={device.max_output_channels} | default-rate={device.default_sample_rate:g} Hz"
            f"{suffix}"
        )


def _print_status(settings: VoiceSettings, discovery: SoundDeviceDiscovery) -> None:
    input_device = discovery.default_input()
    output_device = discovery.default_output()
    configured = AudioFormat(settings.input_sample_rate, settings.input_channels)
    print(f"Voice support installed: {'yes' if _sounddevice_installed() else 'no'}")
    print("Native backend available: yes")
    print(f"Voice enabled: {'yes' if settings.enabled else 'no'}")
    print(f"Input device available: {'yes' if input_device else 'no'}")
    print(f"Output device available: {'yes' if output_device else 'no'}")
    print(
        f"Configured input: {configured.sample_rate} Hz, {configured.channels} channel(s), "
        f"{configured.sample_format.value}"
    )


def _print_unavailable_status(settings: VoiceSettings, error: AudioBackendUnavailableError) -> None:
    configured = AudioFormat(settings.input_sample_rate, settings.input_channels)
    print(f"Voice support installed: {'yes' if _sounddevice_installed() else 'no'}")
    print("Native backend available: no")
    print(f"Voice enabled: {'yes' if settings.enabled else 'no'}")
    print("Input device available: unknown")
    print("Output device available: unknown")
    print(
        f"Configured input: {configured.sample_rate} Hz, {configured.channels} channel(s), "
        f"{configured.sample_format.value}"
    )
    print(f"Backend error: {error}")


def _sounddevice_installed() -> bool:
    try:
        return find_spec("sounddevice") is not None
    except (ImportError, ValueError):
        return False


def _test_input(
    arguments: argparse.Namespace,
    settings: VoiceSettings,
    backend: SoundDeviceBackend,
) -> None:
    audio_format = AudioFormat(settings.input_sample_rate, settings.input_channels)
    device = arguments.device if arguments.device is not None else settings.input_device
    print(
        f"Starting explicit microphone capture for {arguments.duration:g} seconds; "
        "audio will remain in memory only."
    )
    capture = SoundDeviceCapture(
        voice_enabled=settings.enabled,
        duration_limit_seconds=settings.capture_duration_limit_seconds,
        backend=backend,
    )
    try:
        chunk = capture.capture(
            duration_seconds=arguments.duration,
            audio_format=audio_format,
            device=device,
            block_size=settings.block_size,
        )
        print(
            f"Capture complete: {chunk.frame_count} frames, {len(chunk.data)} bytes, "
            f"{chunk.duration_seconds:.3f} seconds."
        )
        if arguments.playback:
            player = SoundDevicePlayback(backend)
            output_device = settings.output_device
            completed = player.play(chunk, device=output_device)
            print("Playback complete." if completed else "Playback interrupted.")
    finally:
        capture.close()
        if "chunk" in locals():
            del chunk


def _test_output(
    arguments: argparse.Namespace,
    settings: VoiceSettings,
    backend: SoundDeviceBackend,
) -> None:
    audio_format = AudioFormat(arguments.sample_rate, 1)
    chunk = _test_tone(audio_format)
    device = arguments.device if arguments.device is not None else settings.output_device
    print("Playing a short, conservatively amplified local test tone.")
    player = SoundDevicePlayback(backend)
    try:
        completed = player.play(chunk, device=device)
        print("Playback complete." if completed else "Playback interrupted.")
    finally:
        player.close()


def _test_tone(audio_format: AudioFormat) -> AudioChunk:
    frame_count = audio_format.frames_for_duration(TEST_TONE_SECONDS)
    peak = int((2**15 - 1) * TEST_TONE_AMPLITUDE)
    data = bytearray()
    for frame in range(frame_count):
        phase = 2 * math.pi * TEST_TONE_HERTZ * frame / audio_format.sample_rate
        value = round(peak * math.sin(phase))
        packed = struct.pack("<h", value)
        data.extend(packed * audio_format.channels)

    return AudioChunk(bytes(data), audio_format)
