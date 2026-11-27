"""Explicit diagnostics for local wake-word infrastructure."""

import argparse
import re
import sys
import wave
from collections.abc import Sequence
from pathlib import Path
from time import monotonic

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.config import load_voice_settings
from kosmos.voice.exceptions import VoiceError, WakeWordError
from kosmos.voice.wakeword.activation import WakeWordActivationPolicy
from kosmos.voice.wakeword.adapters.openwakeword_onnx import (
    OpenWakeWordOnnxDetector,
    backend_available,
)
from kosmos.voice.wakeword.config import WakeWordSettings, load_wakeword_settings
from kosmos.voice.wakeword.framing import WAKE_WORD_AUDIO_FORMAT, WakeWordFramer

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130
MAX_ANALYZE_SECONDS = 300
MAX_CAPTURE_SECONDS = 30
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kosmos-wakeword",
        description="Inspect and explicitly exercise local wake-word infrastructure.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="inspect configuration without loading models")
    subparsers.add_parser("models", help="inspect configured local model paths")
    analyze = subparsers.add_parser("analyze", help="analyze a compatible local WAV")
    analyze.add_argument("--file", required=True, type=Path)
    listen = subparsers.add_parser("listen", help="capture and analyze bounded audio explicitly")
    listen.add_argument("--device", type=int)
    listen.add_argument("--duration", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        return run_command(arguments, settings=load_wakeword_settings())
    except KeyboardInterrupt:
        print("Wake-word diagnostic interrupted; in-memory audio was discarded.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except VoiceError as error:
        print(f"Error: {_sanitize(str(error))}", file=sys.stderr)
        return EXIT_ERROR


def run_command(arguments: argparse.Namespace, *, settings: WakeWordSettings) -> int:
    if arguments.command == "status":
        _print_status(settings)
        return EXIT_OK
    if arguments.command == "models":
        _print_models(settings)
        return EXIT_OK

    detector = OpenWakeWordOnnxDetector(settings)
    try:
        if arguments.command == "analyze":
            chunk = _read_wav(arguments.file)
            mode = "Local WAV"
        elif arguments.command == "listen":
            if arguments.duration <= 0 or arguments.duration > MAX_CAPTURE_SECONDS:
                raise WakeWordError(
                    "Capture duration must be greater than zero and at most 30 seconds"
                )
            detector.load()
            voice = load_voice_settings()
            print(
                f"Opening the microphone for {arguments.duration:g} seconds; "
                "audio remains in memory only."
            )
            from kosmos.voice.audio.adapters.sounddevice import SoundDeviceCapture

            capture = SoundDeviceCapture(
                voice_enabled=voice.enabled,
                duration_limit_seconds=MAX_CAPTURE_SECONDS,
            )
            try:
                chunk = capture.capture(
                    duration_seconds=arguments.duration,
                    audio_format=WAKE_WORD_AUDIO_FORMAT,
                    device=arguments.device if arguments.device is not None else voice.input_device,
                    block_size=voice.block_size,
                )
            finally:
                capture.close()
            mode = "Recorded audio processed after capture"
        else:
            raise AssertionError("argparse accepted an unknown wake-word command")

        _process(chunk, detector, settings, mode)
        return EXIT_OK
    finally:
        detector.close()


def _process(
    chunk: AudioChunk,
    detector: OpenWakeWordOnnxDetector,
    settings: WakeWordSettings,
    mode: str,
) -> None:
    framer = WakeWordFramer()
    policy = WakeWordActivationPolicy(settings)
    windows = framer.push(chunk)
    residual = framer.finish()
    detections = []
    started = monotonic()
    for window in windows:
        result = detector.evaluate(window)
        detection = policy.accept(result)
        if detection is not None:
            detections.append(detection)
            print(
                f"Wake word detected: {detection.phrase} at "
                f"{detection.detection_timestamp_seconds:.3f}s (score={detection.score:.3f})"
            )
    processing_seconds = monotonic() - started
    metrics = detector.metrics
    print(f"Audio duration: {chunk.duration_seconds:.3f} seconds")
    print(f"Processing mode: {mode}")
    print(f"Complete inference windows: {len(windows)}")
    print(f"Residual audio frames not inferred: {0 if residual is None else residual.frame_count}")
    print(f"Warm-up frames: {metrics.warmup_frames}")
    print(f"Detections: {len(detections)}")
    print(f"Suppressed detections: {policy.suppressed_detection_count}")
    print(f"Processing duration: {processing_seconds:.3f}s")
    print(f"Inference Real-Time Factor: {metrics.real_time_factor:.3f}")


def _print_status(settings: WakeWordSettings) -> None:
    paths = (settings.model_path, settings.melspectrogram_path, settings.embedding_path)
    all_models_available = all(path is not None and path.is_file() for path in paths)
    print(f"Wake-word enabled: {_yes_no(settings.enabled)}")
    print(f"Backend: {settings.backend}")
    print(f"Optional dependencies available: {_yes_no(backend_available())}")
    print(f"All local model files available: {_yes_no(all_models_available)}")
    print(f"Phrase: {settings.phrase}")
    print(f"Model identifier: {settings.model_identifier}")
    print(f"Pipeline revision: {settings.model_revision}")
    print(f"Sample rate: {settings.sample_rate} Hz")
    print(f"Frame size: {settings.frame_size} samples")
    print(f"Detection threshold: {settings.threshold:g}")
    print(f"Rearm threshold: {settings.rearm_threshold:g}")
    print(f"Confirmation frames: {settings.confirmation_frames}")
    print(f"Cooldown: {settings.cooldown_seconds:g} seconds")
    print(f"Warm-up frames: {settings.warmup_frames}")
    print("Custom Kosmos model trained: no")
    print("Real wake-word detection verified: no")


def _print_models(settings: WakeWordSettings) -> None:
    for label, path, checksum in (
        ("Classifier", settings.model_path, settings.model_sha256),
        ("Melspectrogram", settings.melspectrogram_path, settings.melspectrogram_sha256),
        ("Embedding", settings.embedding_path, settings.embedding_sha256),
    ):
        print(f"{label} configured: {_yes_no(path is not None)}")
        print(f"{label} available: {_yes_no(bool(path and path.is_file()))}")
        print(f"{label} checksum configured: {_yes_no(checksum is not None)}")


def _read_wav(path: Path) -> AudioChunk:
    if not path.is_file():
        raise WakeWordError("Configured WAV file is unavailable")
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise WakeWordError("Wake-word diagnostics accept only uncompressed PCM WAV files")
            compatible = (
                source.getframerate() == WAKE_WORD_AUDIO_FORMAT.sample_rate
                and source.getnchannels() == WAKE_WORD_AUDIO_FORMAT.channels
                and source.getsampwidth() == 2
            )
            if not compatible:
                raise WakeWordError("Wake-word diagnostics require mono 16000 Hz 16-bit PCM WAV")
            frames = source.getnframes()
            if frames <= 0 or frames > WAKE_WORD_AUDIO_FORMAT.sample_rate * MAX_ANALYZE_SECONDS:
                raise WakeWordError("WAV duration is empty or exceeds the diagnostic limit")
            data = source.readframes(frames)
            if len(data) != frames * WAKE_WORD_AUDIO_FORMAT.bytes_per_frame:
                raise WakeWordError("WAV payload is incomplete")
    except (wave.Error, EOFError, OSError) as error:
        raise WakeWordError("WAV file could not be read safely") from error
    return AudioChunk(data, WAKE_WORD_AUDIO_FORMAT)


def _sanitize(value: str) -> str:
    return _CONTROL_CHARACTERS.sub("", value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
