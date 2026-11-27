from argparse import Namespace

from kosmos.voice.audio.adapters.sounddevice import SoundDeviceBackend
from kosmos.voice.cli import (
    EXIT_OK,
    _print_unavailable_status,
    _test_tone,
    build_parser,
    run_command,
)
from kosmos.voice.config import VoiceSettings
from kosmos.voice.exceptions import AudioBackendUnavailableError

from .audio.test_sounddevice import FakeBackend


def test_audio_parser_exposes_required_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["devices"]).command == "devices"
    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["test-input", "--duration", "2"]).duration == 2
    assert parser.parse_args(["test-output", "--device", "1"]).device == 1


def test_devices_command_does_not_open_streams(capsys: object) -> None:
    backend = FakeBackend()

    result = run_command(
        Namespace(command="devices"),
        settings=VoiceSettings(),
        backend=backend,  # type: ignore[arg-type]
    )

    assert result == EXIT_OK
    assert backend.input_started is False
    assert backend.output_started is False


def test_test_tone_uses_requested_format() -> None:
    from kosmos.voice.audio.models import AudioFormat

    audio_format = AudioFormat(48_000, 1)
    chunk = _test_tone(audio_format)

    assert chunk.format == audio_format
    assert chunk.duration_seconds == 0.25


def test_unavailable_status_distinguishes_native_backend(capsys: object) -> None:
    _print_unavailable_status(
        VoiceSettings(), AudioBackendUnavailableError("PortAudio unavailable")
    )

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Native backend available: no" in output
    assert "Input device available: unknown" in output
    assert "PortAudio unavailable" in output


def _accepts_backend_contract(backend: SoundDeviceBackend) -> SoundDeviceBackend:
    return backend


def test_fake_backend_matches_adapter_contract() -> None:
    assert _accepts_backend_contract(FakeBackend()) is not None  # type: ignore[arg-type]
