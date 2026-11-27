import asyncio
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from kosmos.voice.audio.models import AudioChunk, AudioFormat
from kosmos.voice.exceptions import (
    InvalidRecognitionRequestError,
    SpeechRecognitionBusyError,
    SpeechRecognitionDisabledError,
)
from kosmos.voice.stt.adapters.faster_whisper import (
    FasterWhisperRecognizer,
    load_faster_whisper_backend,
)
from kosmos.voice.stt.config import STTSettings
from kosmos.voice.stt.models import SpeechRecognitionRequest, SpeechRecognitionStatus


class FakeModel:
    def __init__(self, segments: list[object] | None = None) -> None:
        self.segments = segments or []
        self.options: dict[str, object] = {}

    def transcribe(self, audio: object, **options: object) -> tuple[object, object]:
        self.options = options
        return iter(self.segments), SimpleNamespace()


class FakeFactory:
    def __init__(self, model: FakeModel) -> None:
        self.model = model
        self.calls: list[dict[str, object]] = []

    def __call__(self, **keywords: object) -> FakeModel:
        self.calls.append(keywords)
        return self.model


def _settings(tmp_path: Path, **overrides: object) -> STTSettings:
    path = tmp_path / "base"
    path.mkdir()
    (path / "config.json").write_text(json.dumps({"model_type": "whisper"}), encoding="utf-8")
    for name in ("model.bin", "tokenizer.json", "vocabulary.txt"):
        (path / name).write_bytes(b"local")
    values: dict[str, object] = {"enabled": True, "model_path": path}
    values.update(overrides)
    return STTSettings(**values)  # type: ignore[arg-type]


def _request(data: bytes = b"\x01\x00" * 16_000) -> SpeechRecognitionRequest:
    return SpeechRecognitionRequest(AudioChunk(data, AudioFormat(16_000, 1)))


def test_pcm_conversion_preserves_little_endian_reference_values() -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("faster_whisper")
    _factory, convert = load_faster_whisper_backend()

    waveform = convert(b"\x00\x00\xff\x7f\x00\x80\x00\x40")

    assert waveform.tolist() == pytest.approx([0.0, 32767 / 32768, -1.0, 0.5])  # type: ignore[attr-defined]


def test_model_is_loaded_lazily_and_reused(tmp_path: Path) -> None:
    segment = SimpleNamespace(
        start=0,
        end=1,
        text=" Olá",
        avg_logprob=-0.2,
        no_speech_prob=0.1,
    )
    model = FakeModel([segment])
    factory = FakeFactory(model)
    recognizer = FasterWhisperRecognizer(
        _settings(tmp_path), backend_loader=lambda: (factory, lambda data: data)
    )
    assert factory.calls == []
    first = asyncio.run(recognizer.recognize(_request()))
    second = asyncio.run(recognizer.recognize(_request()))
    assert first.text == "Olá" and second.metrics.model_reused
    assert len(factory.calls) == 1
    assert factory.calls[0]["device"] == "cpu"
    assert factory.calls[0]["compute_type"] == "int8"
    assert factory.calls[0]["local_files_only"] is True
    assert model.options["vad_filter"] is False
    assert model.options["task"] == "transcribe"


def test_empty_backend_result_is_not_an_error(tmp_path: Path) -> None:
    recognizer = FasterWhisperRecognizer(
        _settings(tmp_path), backend_loader=lambda: (FakeFactory(FakeModel()), lambda data: data)
    )
    result = asyncio.run(recognizer.recognize(_request()))
    assert result.status is SpeechRecognitionStatus.NO_TRANSCRIPTION


def test_disabled_recognition_is_rejected_before_loading(tmp_path: Path) -> None:
    recognizer = FasterWhisperRecognizer(
        _settings(tmp_path, enabled=False),
        backend_loader=lambda: (FakeFactory(FakeModel()), lambda data: data),
    )
    with pytest.raises(SpeechRecognitionDisabledError):
        asyncio.run(recognizer.recognize(_request()))


@pytest.mark.parametrize(
    "audio",
    [
        AudioChunk(b"\x01\x00", AudioFormat(8_000, 1)),
        AudioChunk(b"\x01\x00\x01\x00", AudioFormat(16_000, 2)),
        AudioChunk(b"\x00\x00" * 100, AudioFormat(16_000, 1)),
    ],
)
def test_incompatible_or_zero_audio_is_rejected(tmp_path: Path, audio: AudioChunk) -> None:
    recognizer = FasterWhisperRecognizer(
        _settings(tmp_path), backend_loader=lambda: (FakeFactory(FakeModel()), lambda data: data)
    )
    with pytest.raises(InvalidRecognitionRequestError):
        asyncio.run(recognizer.recognize(SpeechRecognitionRequest(audio)))


def test_cancellation_keeps_native_operation_reserved(tmp_path: Path) -> None:
    entered = Event()
    release = Event()

    class BlockingModel(FakeModel):
        def transcribe(self, audio: object, **options: object) -> tuple[object, object]:
            def generate() -> object:
                entered.set()
                release.wait()
                yield SimpleNamespace(
                    start=0,
                    end=1,
                    text="Olá",
                    avg_logprob=-0.2,
                    no_speech_prob=0.1,
                )

            return generate(), SimpleNamespace()

    async def scenario() -> None:
        recognizer = FasterWhisperRecognizer(
            _settings(tmp_path),
            backend_loader=lambda: (FakeFactory(BlockingModel()), lambda data: data),
        )
        task = asyncio.create_task(recognizer.recognize(_request()))
        await asyncio.to_thread(entered.wait)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(SpeechRecognitionBusyError):
            await recognizer.recognize(_request())
        release.set()
        await asyncio.sleep(0)
        await asyncio.to_thread(lambda: None)

    asyncio.run(scenario())
