"""Lazy local-only Silero VAD adapter using the public ONNX Runtime API."""

import math
from collections.abc import Callable
from importlib import import_module
from threading import Lock
from time import monotonic

from kosmos.voice.exceptions import (
    InvalidVADModelError,
    InvalidVoiceActivityResultError,
    VADBackendUnavailableError,
    VoiceActivityBusyError,
    VoiceActivityDisabledError,
    VoiceActivityError,
)
from kosmos.voice.vad.config import VADSettings
from kosmos.voice.vad.models import (
    VAD_CONTEXT_SIZE,
    AudioWindow,
    VoiceActivityMetrics,
    VoiceActivityResult,
    VoiceActivityState,
)

BackendLoader = Callable[[], tuple[object, object]]


def load_silero_backend() -> tuple[object, object]:
    """Import optional CPU runtime dependencies only for explicit VAD work."""

    try:
        numpy = import_module("numpy")
        onnxruntime = import_module("onnxruntime")
    except ModuleNotFoundError as error:
        if error.name in {"numpy", "onnxruntime"}:
            raise VADBackendUnavailableError(
                "Voice activity support is not installed; install the 'vad' extra"
            ) from error
        raise VADBackendUnavailableError(
            "Silero VAD could not load one of its runtime dependencies"
        ) from error
    except (ImportError, OSError) as error:
        raise VADBackendUnavailableError(
            "ONNX Runtime is installed, but a native runtime dependency is unavailable"
        ) from error

    return numpy, onnxruntime


class SileroVoiceActivityDetector:
    """Evaluate ordered 16 kHz windows with one private recurrent model state."""

    def __init__(
        self,
        settings: VADSettings,
        *,
        backend_loader: BackendLoader = load_silero_backend,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings
        self._backend_loader = backend_loader
        self._clock = clock
        self._session: object | None = None
        self._numpy: object | None = None
        self._state_tensor: object | None = None
        self._context: object | None = None
        self._operation_lock = Lock()
        self._state = VoiceActivityState.UNLOADED
        self._expected_start_frame = 0
        self._audio_frames_processed = 0
        self._inference_count = 0
        self._model_loading_seconds = 0.0
        self._inference_seconds = 0.0

    @property
    def state(self) -> VoiceActivityState:
        return self._state

    @property
    def metrics(self) -> VoiceActivityMetrics:
        return VoiceActivityMetrics(
            backend=self._settings.backend,
            model_revision=self._settings.model_revision,
            device="cpu",
            sample_rate=self._settings.sample_rate,
            frame_size=self._settings.frame_size,
            audio_frames_processed=self._audio_frames_processed,
            inference_count=self._inference_count,
            model_loading_seconds=self._model_loading_seconds,
            inference_seconds=self._inference_seconds,
        )

    def is_available(self) -> bool:
        try:
            self._settings.validate_model()
            self._backend_loader()
        except VoiceActivityError:
            return False
        return True

    def load(self) -> None:
        """Validate and load one CPU session without starting inference."""

        self._reserve()
        try:
            self._ensure_open()
            self._load_unlocked()
        finally:
            self._operation_lock.release()

    def evaluate(self, window: AudioWindow) -> VoiceActivityResult:
        """Synchronously evaluate one window; callers must use a dedicated worker if needed."""

        if not self._settings.enabled:
            raise VoiceActivityDisabledError(
                "Voice activity detection is disabled; set KOSMOS_VAD_ENABLED=true explicitly"
            )
        self._reserve()
        try:
            self._ensure_open()
            if self._state is VoiceActivityState.FAILED:
                raise VoiceActivityError("Detector state is invalid; reset before reuse")
            if window.start_frame != self._expected_start_frame:
                self._state = VoiceActivityState.FAILED
                raise VoiceActivityError("VAD window timeline is discontinuous; reset is required")
            self._load_unlocked()
            return self._evaluate_unlocked(window)
        finally:
            self._operation_lock.release()

    def reset(self) -> None:
        """Clear recurrent state and sequence metrics while retaining the loaded session."""

        self._reserve()
        try:
            self._ensure_open()
            self._initialize_recurrence()
            self._expected_start_frame = 0
            self._audio_frames_processed = 0
            self._inference_count = 0
            self._inference_seconds = 0.0
            self._state = (
                VoiceActivityState.READY
                if self._session is not None
                else VoiceActivityState.UNLOADED
            )
        finally:
            self._operation_lock.release()

    def close(self) -> None:
        self._reserve()
        try:
            self._session = None
            self._numpy = None
            self._state_tensor = None
            self._context = None
            self._state = VoiceActivityState.CLOSED
        finally:
            self._operation_lock.release()

    def _reserve(self) -> None:
        if not self._operation_lock.acquire(blocking=False):
            raise VoiceActivityBusyError("Voice activity detector already has an active operation")

    def _ensure_open(self) -> None:
        if self._state is VoiceActivityState.CLOSED:
            raise VoiceActivityError("Voice activity detector is closed")

    def _load_unlocked(self) -> None:
        if self._session is not None:
            return

        model = self._settings.validate_model()
        numpy, onnxruntime = self._backend_loader()
        started = self._clock()
        try:
            options = onnxruntime.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
            session = onnxruntime.InferenceSession(
                str(model.path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            self._validate_contract(session)
        except VoiceActivityError:
            raise
        except Exception as error:
            raise VADBackendUnavailableError(
                "Local Silero ONNX model could not be loaded"
            ) from error

        self._numpy = numpy
        self._session = session
        self._initialize_recurrence()
        self._model_loading_seconds = self._clock() - started
        self._state = VoiceActivityState.READY

    def _validate_contract(self, session: object) -> None:
        try:
            inputs = {item.name: item for item in session.get_inputs()}
            outputs = {item.name: item for item in session.get_outputs()}
            providers = session.get_providers()
        except (AttributeError, TypeError) as error:
            raise InvalidVADModelError("ONNX session does not expose model metadata") from error
        if set(inputs) != {"input", "state", "sr"}:
            raise InvalidVADModelError("Silero model input contract is incompatible")
        if set(outputs) != {"output", "stateN"}:
            raise InvalidVADModelError("Silero model output contract is incompatible")
        if providers != ["CPUExecutionProvider"]:
            raise InvalidVADModelError("Silero session must use only CPUExecutionProvider")
        expected_types = {
            "input": "tensor(float)",
            "state": "tensor(float)",
            "sr": "tensor(int64)",
            "output": "tensor(float)",
            "stateN": "tensor(float)",
        }
        for name, metadata in {**inputs, **outputs}.items():
            if getattr(metadata, "type", None) != expected_types[name]:
                raise InvalidVADModelError(f"Silero tensor type for {name} is incompatible")
        expected_ranks = {"input": 2, "state": 3, "sr": 0, "output": 2, "stateN": 3}
        for name, metadata in {**inputs, **outputs}.items():
            shape = getattr(metadata, "shape", None)
            if not isinstance(shape, list) or len(shape) != expected_ranks[name]:
                raise InvalidVADModelError(f"Silero tensor rank for {name} is incompatible")
        if not self._fixed_dimension(inputs["state"].shape[0], 2):
            raise InvalidVADModelError("Silero recurrent state leading dimension is incompatible")
        if not self._fixed_dimension(inputs["state"].shape[2], 128):
            raise InvalidVADModelError("Silero recurrent state width is incompatible")
        if not self._fixed_dimension(outputs["output"].shape[1], 1):
            raise InvalidVADModelError("Silero probability tensor width is incompatible")

    @staticmethod
    def _fixed_dimension(value: object, expected: int) -> bool:
        return value == expected

    def _initialize_recurrence(self) -> None:
        if self._numpy is None:
            self._state_tensor = None
            self._context = None
            return
        numpy = self._numpy
        self._state_tensor = numpy.zeros((2, 1, 128), dtype=numpy.float32)
        self._context = numpy.zeros((1, VAD_CONTEXT_SIZE), dtype=numpy.float32)

    def _evaluate_unlocked(self, window: AudioWindow) -> VoiceActivityResult:
        assert self._numpy is not None
        assert self._session is not None
        assert self._state_tensor is not None and self._context is not None
        numpy = self._numpy
        samples = numpy.frombuffer(window.inference_pcm, dtype="<i2")
        frame = samples.astype(numpy.float32).reshape(1, -1) / 32768.0
        model_input = numpy.concatenate((self._context, frame), axis=1)
        sample_rate = numpy.array(self._settings.sample_rate, dtype=numpy.int64)
        started = self._clock()
        try:
            probability_output, state_output = self._session.run(
                ["output", "stateN"],
                {"input": model_input, "state": self._state_tensor, "sr": sample_rate},
            )
            probability = self._validate_probability(probability_output)
            self._validate_state(state_output)
        except InvalidVoiceActivityResultError:
            self._state = VoiceActivityState.FAILED
            raise
        except Exception as error:
            self._state = VoiceActivityState.FAILED
            raise VoiceActivityError("Silero ONNX inference failed; reset is required") from error
        inference_seconds = self._clock() - started

        self._state_tensor = state_output.copy()
        self._context = model_input[:, -VAD_CONTEXT_SIZE:].copy()
        self._expected_start_frame = window.end_frame
        self._audio_frames_processed += window.audio.frame_count
        self._inference_count += 1
        self._inference_seconds += inference_seconds
        return VoiceActivityResult(
            probability=probability,
            start_frame=window.start_frame,
            audio_frame_count=window.audio.frame_count,
            inference_seconds=inference_seconds,
        )

    def _validate_probability(self, output: object) -> float:
        assert self._numpy is not None
        array = self._numpy.asarray(output)
        if array.shape != (1, 1):
            raise InvalidVoiceActivityResultError("Silero probability tensor shape is invalid")
        probability = float(array[0, 0])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise InvalidVoiceActivityResultError("Silero returned an invalid speech probability")
        return probability

    def _validate_state(self, output: object) -> None:
        assert self._numpy is not None
        array = self._numpy.asarray(output)
        if array.shape != (2, 1, 128) or not self._numpy.isfinite(array).all():
            raise InvalidVoiceActivityResultError("Silero recurrent state tensor is invalid")
        if array.dtype != self._numpy.float32:
            raise InvalidVoiceActivityResultError("Silero recurrent state must use float32")


def backend_available() -> bool:
    """Report optional package availability without creating an inference session."""

    try:
        load_silero_backend()
    except VADBackendUnavailableError:
        return False
    return True
