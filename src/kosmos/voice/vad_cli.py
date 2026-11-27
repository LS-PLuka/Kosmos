"""Explicit development diagnostics for local voice activity detection."""

import argparse
import re
import sys
import wave
from collections.abc import Sequence
from pathlib import Path
from time import monotonic

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.config import load_voice_settings
from kosmos.voice.exceptions import VoiceActivityError, VoiceError
from kosmos.voice.vad.adapters.silero import (
    SileroVoiceActivityDetector,
    backend_available,
)
from kosmos.voice.vad.config import VADSettings, load_vad_settings
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT, AudioFramer
from kosmos.voice.vad.models import SpeechEventType, Utterance
from kosmos.voice.vad.segmentation import DeterministicSpeechSegmenter

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130
MAX_ANALYZE_SECONDS = 300
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kosmos-vad",
        description="Inspect and explicitly exercise local voice activity detection.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="inspect configuration without loading a model")
    analyze = subparsers.add_parser("analyze", help="analyze a compatible local WAV")
    analyze.add_argument("--file", required=True, type=Path)
    listen = subparsers.add_parser("listen", help="capture and analyze bounded audio explicitly")
    listen.add_argument("--device", type=int)
    listen.add_argument("--duration", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        return run_command(arguments, settings=load_vad_settings())
    except KeyboardInterrupt:
        print(
            "VAD diagnostic interrupted; retained in-memory audio was discarded.",
            file=sys.stderr,
        )
        return EXIT_INTERRUPTED
    except VoiceError as error:
        print(f"Error: {_sanitize(str(error))}", file=sys.stderr)
        return EXIT_ERROR


def run_command(arguments: argparse.Namespace, *, settings: VADSettings) -> int:
    if arguments.command == "status":
        _print_status(settings)
        return EXIT_OK

    detector = SileroVoiceActivityDetector(settings)
    try:
        if arguments.command == "analyze":
            chunk = _read_wav(arguments.file)
            mode = "Local WAV"
        elif arguments.command == "listen":
            if arguments.duration <= 0 or arguments.duration > settings.max_utterance_seconds:
                raise VoiceActivityError("Capture duration is outside the VAD utterance limit")
            detector.load()
            voice = load_voice_settings()
            print(
                f"Opening the microphone for {arguments.duration:g} seconds; "
                "audio remains in memory only."
            )
            from kosmos.voice.audio.adapters.sounddevice import SoundDeviceCapture

            capture = SoundDeviceCapture(
                voice_enabled=voice.enabled,
                duration_limit_seconds=settings.max_utterance_seconds,
            )
            try:
                chunk = capture.capture(
                    duration_seconds=arguments.duration,
                    audio_format=VAD_AUDIO_FORMAT,
                    device=arguments.device if arguments.device is not None else voice.input_device,
                    block_size=voice.block_size,
                )
            finally:
                capture.close()
            mode = "Recorded audio processed after capture"
        else:
            raise AssertionError("argparse accepted an unknown VAD command")

        _process(chunk, detector, settings, mode)
        return EXIT_OK
    finally:
        detector.close()


def _process(
    chunk: AudioChunk,
    detector: SileroVoiceActivityDetector,
    settings: VADSettings,
    mode: str,
) -> None:
    framer = AudioFramer()
    segmenter = DeterministicSpeechSegmenter(settings)
    windows = (*framer.push(chunk), *framer.finish())
    events = []
    utterances: list[Utterance] = []
    started = monotonic()
    for window in windows:
        result = segmenter.accept(window, detector.evaluate(window))
        events.extend(result.events)
        utterances.extend(result.utterances)
    final = segmenter.finish()
    events.extend(final.events)
    utterances.extend(final.utterances)
    processing_seconds = monotonic() - started

    print(f"Audio duration: {chunk.duration_seconds:.3f} seconds")
    print(f"Processing mode: {mode}")
    for event in events:
        if event.type is SpeechEventType.SPEECH_STARTED:
            print(f"Speech started: {event.timestamp_seconds:.3f}s")
        elif event.type is SpeechEventType.SPEECH_ENDED:
            print(f"Speech ended: {event.timestamp_seconds:.3f}s")
        elif event.type is SpeechEventType.UTTERANCE_DISCARDED:
            print(f"Utterance discarded: {event.end_reason.value}")
    for utterance in utterances:
        print(f"Utterance completed: {utterance.duration_seconds:.3f}s")
        print(f"End reason: {utterance.end_reason.value}")
    metrics = detector.metrics
    real_time_factor = processing_seconds / chunk.duration_seconds
    print(f"Completed utterances: {len(utterances)}")
    print(f"Inference frames: {metrics.inference_count}")
    print(f"Processing duration: {processing_seconds:.3f}s")
    print(f"Real-Time Factor: {real_time_factor:.3f}")


def _print_status(settings: VADSettings) -> None:
    model_available = bool(settings.model_path and settings.model_path.is_file())
    print(f"VAD enabled: {_yes_no(settings.enabled)}")
    print(f"Backend: {settings.backend}")
    print(f"Optional dependencies available: {_yes_no(backend_available())}")
    print(f"Local model file available: {_yes_no(model_available)}")
    print(f"Model revision: {settings.model_revision}")
    print(f"Checksum configured: {_yes_no(settings.model_sha256 is not None)}")
    print(f"Sample rate: {settings.sample_rate} Hz")
    print(f"Frame size: {settings.frame_size} samples")
    print(f"Speech threshold: {settings.speech_threshold:g}")
    print(f"End speech threshold: {settings.end_speech_threshold:g}")
    print(f"Minimum speech duration: {settings.min_speech_ms} ms")
    print(f"Minimum silence duration: {settings.min_silence_ms} ms")
    print(f"Pre-roll: {settings.pre_roll_ms} ms")
    print(f"Post-roll: {settings.post_roll_ms} ms")
    print(f"Maximum utterance duration: {settings.max_utterance_seconds:g} seconds")
    print("Real VAD inference verified: no")


def _read_wav(path: Path) -> AudioChunk:
    if not path.is_file():
        raise VoiceActivityError("Configured WAV file is unavailable")
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise VoiceActivityError("VAD accepts only uncompressed PCM WAV files")
            compatible = (
                source.getframerate() == VAD_AUDIO_FORMAT.sample_rate
                and source.getnchannels() == VAD_AUDIO_FORMAT.channels
                and source.getsampwidth() == 2
            )
            if not compatible:
                raise VoiceActivityError("VAD requires mono 16000 Hz 16-bit PCM WAV")
            frames = source.getnframes()
            if frames <= 0 or frames > VAD_AUDIO_FORMAT.sample_rate * MAX_ANALYZE_SECONDS:
                raise VoiceActivityError("WAV duration is empty or exceeds the diagnostic limit")
            data = source.readframes(frames)
            if len(data) != frames * VAD_AUDIO_FORMAT.bytes_per_frame:
                raise VoiceActivityError("WAV payload is incomplete")
    except (wave.Error, EOFError, OSError) as error:
        raise VoiceActivityError("WAV file could not be read safely") from error

    return AudioChunk(data, VAD_AUDIO_FORMAT)


def _sanitize(value: str) -> str:
    return _CONTROL_CHARACTERS.sub("", value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
