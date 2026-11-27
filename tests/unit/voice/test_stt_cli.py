import wave
from pathlib import Path

import pytest

from kosmos.voice.exceptions import SpeechRecognitionError
from kosmos.voice.stt.config import STTSettings
from kosmos.voice.stt_cli import _print_status, _read_wav, _sanitize, build_parser


def test_parser_exposes_stt_diagnostics() -> None:
    parser = build_parser()
    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["models"]).command == "models"
    assert parser.parse_args(["transcribe", "--file", "sample.wav"]).file == Path("sample.wav")
    assert parser.parse_args(["listen"]).duration == 5.0


def test_status_does_not_require_model_or_backend(capsys: object) -> None:
    _print_status(STTSettings())
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "STT enabled: no" in output
    assert "Model configuration valid: no" in output
    assert "Real recognition verified: no" in output


def test_read_wav_accepts_only_bounded_foundation_pcm(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * 16_000)
    chunk = _read_wav(path, 30)
    assert chunk.frame_count == 16_000


def test_read_wav_rejects_incompatible_format(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * 100)
    with pytest.raises(SpeechRecognitionError, match="requires mono"):
        _read_wav(path, 30)


def test_terminal_output_is_sanitized() -> None:
    assert _sanitize("Olá\x1b[31m") == "Olá[31m"
