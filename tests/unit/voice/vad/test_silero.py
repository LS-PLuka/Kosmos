from pathlib import Path
from types import SimpleNamespace

import pytest

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import InvalidVoiceActivityResultError, VoiceActivityError
from kosmos.voice.vad.adapters.silero import SileroVoiceActivityDetector
from kosmos.voice.vad.config import VADSettings
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT
from kosmos.voice.vad.models import AudioWindow, VoiceActivityState

numpy = pytest.importorskip("numpy")


class FakeOptions:
    intra_op_num_threads = 0
    inter_op_num_threads = 0
    execution_mode = None


class FakeSession:
    def __init__(self, probability: float = 0.8) -> None:
        self.probability = probability
        self.inputs: list[dict[str, object]] = []

    def get_inputs(self) -> list[object]:
        return [
            SimpleNamespace(name="input", type="tensor(float)", shape=[None, None]),
            SimpleNamespace(name="state", type="tensor(float)", shape=[2, None, 128]),
            SimpleNamespace(name="sr", type="tensor(int64)", shape=[]),
        ]

    def get_outputs(self) -> list[object]:
        return [
            SimpleNamespace(name="output", type="tensor(float)", shape=[None, 1]),
            SimpleNamespace(name="stateN", type="tensor(float)", shape=[2, None, 128]),
        ]

    def get_providers(self) -> list[str]:
        return ["CPUExecutionProvider"]

    def run(self, outputs: list[str], inputs: dict[str, object]) -> list[object]:
        assert outputs == ["output", "stateN"]
        self.inputs.append(inputs)
        probability = numpy.array([[self.probability]], dtype=numpy.float32)
        state = numpy.asarray(inputs["state"], dtype=numpy.float32) + 1
        return [probability, state]


class FakeRuntime:
    class ExecutionMode:
        ORT_SEQUENTIAL = "sequential"

    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.options: FakeOptions | None = None
        self.providers: list[str] | None = None

    def SessionOptions(self) -> FakeOptions:
        self.options = FakeOptions()
        return self.options

    def InferenceSession(
        self, path: str, *, sess_options: FakeOptions, providers: list[str]
    ) -> FakeSession:
        assert Path(path).is_file()
        self.options = sess_options
        self.providers = providers
        return self.session


def _settings(tmp_path: Path) -> VADSettings:
    model = tmp_path / "silero.onnx"
    model.write_bytes(b"fake-onnx")
    return VADSettings(enabled=True, model_path=model)


def _window(index: int, sample: int = 16_384) -> AudioWindow:
    data = sample.to_bytes(2, "little", signed=True) * 512
    return AudioWindow(AudioChunk(data, VAD_AUDIO_FORMAT), index * 512)


def test_session_configuration_context_and_state_are_preserved(tmp_path: Path) -> None:
    session = FakeSession()
    runtime = FakeRuntime(session)
    detector = SileroVoiceActivityDetector(
        _settings(tmp_path), backend_loader=lambda: (numpy, runtime)
    )
    assert detector.state is VoiceActivityState.UNLOADED
    first = detector.evaluate(_window(0))
    detector.evaluate(_window(1, 8_192))

    assert first.probability == pytest.approx(0.8)
    assert runtime.providers == ["CPUExecutionProvider"]
    assert runtime.options is not None
    assert runtime.options.intra_op_num_threads == 1
    assert runtime.options.inter_op_num_threads == 1
    assert runtime.options.execution_mode == "sequential"
    assert numpy.asarray(session.inputs[0]["input"]).shape == (1, 576)
    assert numpy.asarray(session.inputs[0]["input"])[0, :64].tolist() == [0.0] * 64
    assert numpy.asarray(session.inputs[1]["input"])[0, :64].tolist() == [0.5] * 64
    assert (
        numpy.asarray(session.inputs[1]["state"]).tolist()
        == numpy.ones((2, 1, 128), dtype=numpy.float32).tolist()
    )
    assert detector.metrics.inference_count == 2


def test_reset_clears_recurrence_but_reuses_session(tmp_path: Path) -> None:
    session = FakeSession()
    runtime = FakeRuntime(session)
    detector = SileroVoiceActivityDetector(
        _settings(tmp_path), backend_loader=lambda: (numpy, runtime)
    )
    detector.evaluate(_window(0))
    detector.reset()
    detector.evaluate(_window(0, 8_192))
    assert (
        numpy.asarray(session.inputs[1]["state"]).tolist()
        == numpy.zeros((2, 1, 128), dtype=numpy.float32).tolist()
    )
    assert numpy.asarray(session.inputs[1]["input"])[0, :64].tolist() == [0.0] * 64


def test_invalid_probability_fails_sequence_until_reset(tmp_path: Path) -> None:
    session = FakeSession(float("nan"))
    detector = SileroVoiceActivityDetector(
        _settings(tmp_path), backend_loader=lambda: (numpy, FakeRuntime(session))
    )
    with pytest.raises(InvalidVoiceActivityResultError):
        detector.evaluate(_window(0))
    assert detector.state is VoiceActivityState.FAILED
    with pytest.raises(VoiceActivityError, match="reset"):
        detector.evaluate(_window(0))
    detector.reset()
    assert detector.state is VoiceActivityState.READY


def test_close_prevents_further_operations(tmp_path: Path) -> None:
    detector = SileroVoiceActivityDetector(
        _settings(tmp_path), backend_loader=lambda: (numpy, FakeRuntime(FakeSession()))
    )
    detector.close()
    with pytest.raises(VoiceActivityError, match="closed"):
        detector.load()
