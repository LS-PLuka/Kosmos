from dataclasses import dataclass

import pytest

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import (
    InvalidWakeWordInputError,
    InvalidWakeWordResultError,
    WakeWordDisabledError,
    WakeWordError,
)
from kosmos.voice.wakeword.adapters.openwakeword_onnx import OpenWakeWordOnnxDetector
from kosmos.voice.wakeword.config import WakeWordSettings
from kosmos.voice.wakeword.framing import WAKE_WORD_AUDIO_FORMAT
from kosmos.voice.wakeword.models import WakeWordOperationalState, WakeWordWindow

np = pytest.importorskip("numpy")


@dataclass
class Metadata:
    name: str
    shape: list[object]
    type: str = "tensor(float)"


class FakeSession:
    def __init__(self, kind: str, scores: list[float]) -> None:
        self.kind = kind
        self.scores = scores
        self.calls: list[dict[str, object]] = []

    def get_providers(self) -> list[str]:
        return ["CPUExecutionProvider"]

    def get_inputs(self) -> list[Metadata]:
        if self.kind == "mel":
            return [Metadata("input", [1, "samples"])]
        if self.kind == "embedding":
            return [Metadata("input_1", [1, 76, 32, 1])]
        return [Metadata("features", [1, 16, 96])]

    def get_outputs(self) -> list[Metadata]:
        if self.kind == "mel":
            return [Metadata("output", [1, 5, 32])]
        if self.kind == "embedding":
            return [Metadata("output", [1, 96])]
        return [Metadata("output", [1, 1])]

    def run(self, outputs: object, inputs: dict[str, object]) -> list[np.ndarray]:
        self.calls.append(inputs)
        if self.kind == "mel":
            return [np.ones((1, 5, 32), dtype=np.float32)]
        if self.kind == "embedding":
            return [np.ones((1, 96), dtype=np.float32)]
        score = self.scores.pop(0) if self.scores else 0.25
        return [np.array([[score]], dtype=np.float32)]


class FakeRuntime:
    class SessionOptions:
        pass

    class ExecutionMode:
        ORT_SEQUENTIAL = "sequential"

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.sessions: list[FakeSession] = []

    def InferenceSession(self, path: str, **kwargs: object) -> FakeSession:
        if "mel" in path:
            kind = "mel"
        elif "embedding" in path:
            kind = "embedding"
        else:
            kind = "classifier"
        session = FakeSession(kind, self.scores)
        self.sessions.append(session)
        assert kwargs["providers"] == ["CPUExecutionProvider"]
        return session


def _settings(tmp_path, **overrides: object) -> WakeWordSettings:
    classifier = tmp_path / "kosmos.onnx"
    mel = tmp_path / "mel.onnx"
    embedding = tmp_path / "embedding.onnx"
    for path in (classifier, mel, embedding):
        path.write_bytes(b"model")
    values = {
        "enabled": True,
        "model_path": classifier,
        "melspectrogram_path": mel,
        "embedding_path": embedding,
        "warmup_frames": 0,
    }
    values.update(overrides)
    return WakeWordSettings(**values)


def _window(index: int) -> WakeWordWindow:
    audio = AudioChunk(b"\x00\x00" * 1_280, WAKE_WORD_AUDIO_FORMAT)
    return WakeWordWindow(audio, index * 1_280)


def test_adapter_loads_three_cpu_sessions_and_runs_pinned_pipeline(tmp_path) -> None:
    runtime = FakeRuntime([0.75])
    detector = OpenWakeWordOnnxDetector(
        _settings(tmp_path), backend_loader=lambda: (np, runtime), clock=lambda: 1.0
    )

    result = detector.evaluate(_window(0))

    assert result.score == pytest.approx(0.75)
    assert result.ready is True
    assert detector.available is True
    assert detector.model_identifier == "kosmos"
    assert detector.state is WakeWordOperationalState.READY
    assert len(runtime.sessions) == 3
    mel_input = runtime.sessions[0].calls[0]["input"]
    classifier_input = runtime.sessions[2].calls[0]["features"]
    assert mel_input.shape == (1, 1_280)
    assert classifier_input.shape == (1, 16, 96)
    assert detector.metrics.audio_frames_processed == 1_280


def test_adapter_marks_first_five_frames_as_warmup(tmp_path) -> None:
    detector = OpenWakeWordOnnxDetector(
        _settings(tmp_path, warmup_frames=5),
        backend_loader=lambda: (np, FakeRuntime([0.9] * 6)),
    )

    results = [detector.evaluate(_window(index)) for index in range(6)]

    assert [result.ready for result in results] == [False] * 5 + [True]
    assert detector.metrics.warmup_frames == 5


def test_adapter_requires_explicit_enablement(tmp_path) -> None:
    settings = _settings(tmp_path)
    disabled = WakeWordSettings(
        model_path=settings.model_path,
        melspectrogram_path=settings.melspectrogram_path,
        embedding_path=settings.embedding_path,
    )
    detector = OpenWakeWordOnnxDetector(disabled, backend_loader=lambda: (np, FakeRuntime([0.9])))

    with pytest.raises(WakeWordDisabledError):
        detector.evaluate(_window(0))


def test_adapter_rejects_discontinuity_and_invalid_score(tmp_path) -> None:
    detector = OpenWakeWordOnnxDetector(
        _settings(tmp_path), backend_loader=lambda: (np, FakeRuntime([float("nan")]))
    )

    with pytest.raises(InvalidWakeWordInputError):
        detector.evaluate(_window(1))
    with pytest.raises(InvalidWakeWordResultError):
        detector.evaluate(_window(0))
    assert detector.state is WakeWordOperationalState.FAILED


def test_reset_retains_sessions_and_close_forbids_inference(tmp_path) -> None:
    runtime = FakeRuntime([0.2, 0.3])
    detector = OpenWakeWordOnnxDetector(_settings(tmp_path), backend_loader=lambda: (np, runtime))
    detector.evaluate(_window(0))

    detector.reset()
    detector.evaluate(_window(0))
    detector.close()

    assert len(runtime.sessions) == 3
    assert detector.state is WakeWordOperationalState.CLOSED
    with pytest.raises(WakeWordError, match="closed"):
        detector.evaluate(_window(0))
