from argparse import Namespace

from kosmos.voice.wakeword.config import WakeWordSettings
from kosmos.voice.wakeword_cli import EXIT_OK, build_parser, run_command


def test_parser_exposes_bounded_diagnostic_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["models"]).command == "models"
    assert parser.parse_args(["analyze", "--file", "sample.wav"]).command == "analyze"
    assert parser.parse_args(["listen"]).duration == 5.0


def test_status_reports_pending_real_validation(monkeypatch, capsys) -> None:
    monkeypatch.setattr("kosmos.voice.wakeword_cli.backend_available", lambda: True)

    result = run_command(Namespace(command="status"), settings=WakeWordSettings())

    output = capsys.readouterr().out
    assert result == EXIT_OK
    assert "Wake-word enabled: no" in output
    assert "Optional dependencies available: yes" in output
    assert "Custom Kosmos model trained: no" in output
    assert "Real wake-word detection verified: no" in output


def test_models_does_not_load_or_validate_missing_files(capsys) -> None:
    result = run_command(Namespace(command="models"), settings=WakeWordSettings())

    output = capsys.readouterr().out
    assert result == EXIT_OK
    assert "Classifier configured: no" in output
    assert "Melspectrogram available: no" in output
