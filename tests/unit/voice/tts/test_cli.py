import json
from argparse import Namespace
from pathlib import Path

from kosmos.voice.tts.config import TTSSettings
from kosmos.voice.tts_cli import EXIT_OK, _print_status, _print_voices, build_parser, run_command


def _settings(tmp_path: Path) -> TTSSettings:
    model = tmp_path / "voice.onnx"
    config = tmp_path / "config.json"
    executable = tmp_path / "piper"
    model.write_bytes(b"model")
    executable.write_bytes(b"executable")
    config.write_text(
        json.dumps(
            {
                "audio": {"sample_rate": 22050},
                "language": {"code": "pt-br"},
                "num_speakers": 1,
                "espeak": {"voice": "pt-br"},
                "phoneme_id_map": {"_": [0]},
            }
        ),
        encoding="utf-8",
    )
    return TTSSettings(executable=executable, model_path=model, config_path=config)


def test_tts_parser_exposes_diagnostic_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["voices"]).command == "voices"
    assert parser.parse_args(["synthesize", "--text", "Olá"]).text == "Olá"
    assert parser.parse_args(["speak", "--text", "Olá"]).command == "speak"


def test_status_does_not_start_synthesis_or_playback(tmp_path: Path, capsys: object) -> None:
    _print_status(_settings(tmp_path))

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Backend executable available: yes" in output
    assert "Configured sample rate: 22050" in output
    assert "Real synthesis verified: no" in output


def test_status_reports_missing_configuration_without_failure(capsys: object) -> None:
    _print_status(TTSSettings())

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Voice model available: no" in output
    assert "Voice configuration valid: no" in output


def test_voices_lists_only_valid_configured_voice(tmp_path: Path, capsys: object) -> None:
    _print_voices(_settings(tmp_path))

    assert "razo | language=pt-br | sample-rate=22050 Hz" in capsys.readouterr().out  # type: ignore[attr-defined]


def test_status_command_completes_without_process_or_device(tmp_path: Path) -> None:
    import asyncio

    result = asyncio.run(run_command(Namespace(command="status"), settings=_settings(tmp_path)))

    assert result == EXIT_OK
