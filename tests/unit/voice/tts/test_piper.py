import asyncio
import json
import sys
from pathlib import Path

import pytest

from kosmos.voice.exceptions import (
    InvalidSynthesizedAudioError,
    SpeechSynthesisError,
    SynthesisTimeoutError,
    TTSBackendUnavailableError,
)
from kosmos.voice.tts.adapters.piper import PiperExternalProcessSynthesizer
from kosmos.voice.tts.config import TTSSettings
from kosmos.voice.tts.models import SpeechSynthesisRequest, SpeechVoice


class FakeReader:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def read(self, size: int) -> bytes:
        result = self.data[:size]
        self.data = self.data[size:]
        return result


class FakeWriter:
    def __init__(self) -> None:
        self.data = b""
        self.closed = False

    def write(self, data: bytes) -> None:
        self.data += data

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass


class FakeProcess:
    def __init__(
        self, stdout: bytes, stderr: bytes = b"", return_code: int = 0, *, hangs: bool = False
    ) -> None:
        self.stdin = FakeWriter()
        self.stdout = FakeReader(stdout)
        self.stderr = FakeReader(stderr)
        self.returncode: int | None = None
        self.expected_return_code = return_code
        self.hangs = hangs
        self.killed = False

    async def wait(self) -> int:
        if self.hangs and not self.killed:
            await asyncio.Future()
        self.returncode = self.expected_return_code
        return self.returncode

    def kill(self) -> None:
        self.killed = True


class FakeFactory:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.arguments: tuple[str, ...] = ()
        self.keywords: dict[str, object] = {}

    async def __call__(self, *arguments: str, **keywords: object) -> FakeProcess:
        self.arguments = arguments
        self.keywords = keywords
        return self.process


def _settings(tmp_path: Path, **overrides: object) -> TTSSettings:
    model = tmp_path / "voice.onnx"
    config = tmp_path / "config.json"
    model.write_bytes(b"model")
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
    values: dict[str, object] = {
        "enabled": True,
        "executable": Path(sys.executable),
        "model_path": model,
        "config_path": config,
    }
    values.update(overrides)
    return TTSSettings(**values)  # type: ignore[arg-type]


def _request() -> SpeechSynthesisRequest:
    return SpeechSynthesisRequest("Olá, senhor.", SpeechVoice("razo"))


def test_piper_builds_structured_arguments_and_writes_utf8_stdin(tmp_path: Path) -> None:
    process = FakeProcess(b"\x00\x00" * 22_050)
    factory = FakeFactory(process)
    clock_values = iter((10.0, 10.5))
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path), process_factory=factory, clock=lambda: next(clock_values)
    )

    result = asyncio.run(synthesizer.synthesize(_request()))

    assert "--output-raw" in factory.arguments
    assert factory.arguments[0] == str(Path(sys.executable).resolve())
    assert factory.keywords["stdin"] == asyncio.subprocess.PIPE
    assert "shell" not in factory.keywords
    assert process.stdin.data == "Olá, senhor.\n".encode()
    assert result.audio.format.sample_rate == 22_050
    assert result.metrics.process_duration_seconds == 0.5
    assert result.metrics.real_time_factor == 0.5


def test_piper_rejects_disabled_synthesis_without_starting_process(tmp_path: Path) -> None:
    factory = FakeFactory(FakeProcess(b"\x00\x00"))
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path, enabled=False), process_factory=factory
    )

    with pytest.raises(TTSBackendUnavailableError, match="disabled"):
        asyncio.run(synthesizer.synthesize(_request()))

    assert factory.arguments == ()


def test_piper_rejects_command_scripts(tmp_path: Path) -> None:
    settings = _settings(tmp_path, executable=tmp_path / "piper.cmd")

    with pytest.raises(TTSBackendUnavailableError, match="not allowed"):
        asyncio.run(PiperExternalProcessSynthesizer(settings).synthesize(_request()))


def test_piper_translates_process_start_failure(tmp_path: Path) -> None:
    async def fail(*arguments: str, **keywords: object) -> FakeProcess:
        raise OSError("private path")

    synthesizer = PiperExternalProcessSynthesizer(_settings(tmp_path), process_factory=fail)

    with pytest.raises(TTSBackendUnavailableError, match="could not start"):
        asyncio.run(synthesizer.synthesize(_request()))


@pytest.mark.parametrize(
    ("process", "error", "message"),
    [
        (FakeProcess(b""), InvalidSynthesizedAudioError, "empty"),
        (FakeProcess(b"\x00"), InvalidSynthesizedAudioError, "partial"),
        (FakeProcess(b"\x00\x00", return_code=2), SpeechSynthesisError, "exited"),
    ],
)
def test_piper_rejects_invalid_process_results(
    tmp_path: Path, process: FakeProcess, error: type[Exception], message: str
) -> None:
    clock_values = iter((1.0, 2.0))
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path),
        process_factory=FakeFactory(process),
        clock=lambda: next(clock_values),
    )

    with pytest.raises(error, match=message):
        asyncio.run(synthesizer.synthesize(_request()))


def test_piper_limits_audio_during_stream_consumption(tmp_path: Path) -> None:
    process = FakeProcess(b"\x00\x00" * 10)
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path, max_audio_bytes=8), process_factory=FakeFactory(process)
    )

    with pytest.raises(InvalidSynthesizedAudioError, match="exceeded"):
        asyncio.run(synthesizer.synthesize(_request()))

    assert process.killed or process.returncode is not None


def test_piper_limits_stderr_without_exposing_content(tmp_path: Path) -> None:
    process = FakeProcess(b"\x00\x00", stderr=b"private" * 1000)
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path, max_stderr_bytes=10), process_factory=FakeFactory(process)
    )

    with pytest.raises(SpeechSynthesisError, match="stderr exceeded") as raised:
        asyncio.run(synthesizer.synthesize(_request()))

    assert "private" not in str(raised.value)


def test_piper_kills_process_after_timeout(tmp_path: Path) -> None:
    process = FakeProcess(b"", hangs=True)
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path, timeout_seconds=0.1), process_factory=FakeFactory(process)
    )

    with pytest.raises(SynthesisTimeoutError, match="timeout"):
        asyncio.run(synthesizer.synthesize(_request()))

    assert process.killed


def test_piper_kills_process_after_cancellation(tmp_path: Path) -> None:
    process = FakeProcess(b"", hangs=True)
    synthesizer = PiperExternalProcessSynthesizer(
        _settings(tmp_path), process_factory=FakeFactory(process)
    )

    async def cancel_synthesis() -> None:
        task = asyncio.create_task(synthesizer.synthesize(_request()))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_synthesis())

    assert process.killed


def test_piper_close_prevents_later_synthesis(tmp_path: Path) -> None:
    synthesizer = PiperExternalProcessSynthesizer(_settings(tmp_path))
    asyncio.run(synthesizer.close())

    with pytest.raises(TTSBackendUnavailableError, match="closed"):
        asyncio.run(synthesizer.synthesize(_request()))
