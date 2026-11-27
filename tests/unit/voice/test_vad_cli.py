import wave
from pathlib import Path

import pytest

from kosmos.voice.exceptions import VoiceActivityError
from kosmos.voice.vad.config import VADSettings
from kosmos.voice.vad_cli import _print_status, _read_wav, _sanitize, build_parser


def test_parser_exposes_vad_diagnostics() -> None:
    parser = build_parser()
    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["analyze", "--file", "sample.wav"]).file == Path("sample.wav")
    assert parser.parse_args(["listen"]).duration == 5.0


def test_status_does_not_require_model(capsys: pytest.CaptureFixture[str]) -> None:
    _print_status(VADSettings())
    output = capsys.readouterr().out
    assert "VAD enabled: no" in output
    assert "Local model file available: no" in output
    assert "Real VAD inference verified: no" in output


def test_read_wav_accepts_only_bounded_foundation_pcm(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * 16_000)
    chunk = _read_wav(path)
    assert chunk.frame_count == 16_000


def test_read_wav_rejects_incompatible_format(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * 100)
    with pytest.raises(VoiceActivityError, match="requires mono"):
        _read_wav(path)


def test_terminal_output_is_sanitized() -> None:
    assert _sanitize("model\x1b[31m") == "model[31m"
