"""Minimal ONNX pipeline adapted from openWakeWord v0.6.0 (commit c8ef691)."""

import math
from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic
from types import ModuleType

from kosmos.voice.exceptions import (
    InvalidWakeWordInputError,
    InvalidWakeWordModelError,
    InvalidWakeWordResultError,
    WakeWordBackendUnavailableError,
    WakeWordBusyError,
    WakeWordDisabledError,
    WakeWordError,
)
from kosmos.voice.wakeword.config import WakeWordSettings
from kosmos.voice.wakeword.models import (
    WAKE_WORD_SAMPLE_RATE,
    WakeWordMetrics,
    WakeWordOperationalState,
    WakeWordResult,
    WakeWordWindow,
)

MELSPECTROGRAM_CONTEXT_SAMPLES = 480
MELSPECTROGRAM_CONTEXT_FRAMES = 76
MELSPECTROGRAM_BINS = 32
EMBEDDING_SIZE = 96
RAW_BUFFER_SAMPLES = WAKE_WORD_SAMPLE_RATE * 10
MELSPECTROGRAM_BUFFER_FRAMES = 970
EMBEDDING_BUFFER_FRAMES = 120

BackendLoader = Callable[[], tuple[ModuleType, ModuleType]]


def load_onnx_backend() -> tuple[ModuleType, ModuleType]:
    """Load optional runtime packages without constructing a session."""

    try:
        import numpy
        import onnxruntime
    except (ImportError, OSError) as error:
        raise WakeWordBackendUnavailableError(
            "Wake-word support requires the 'wakeword' extra"
        ) from error
    return numpy, onnxruntime


class OpenWakeWordOnnxDetector:
    """Own three CPU-only ONNX sessions and one ordered streaming sequence."""

    def __init__(
        self,
        settings: WakeWordSettings,
        *,
        backend_loader: BackendLoader = load_onnx_backend,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings
        self._backend_loader = backend_loader
        self._clock = clock
        self._operation_lock = Lock()
        self._numpy: ModuleType | None = None
        self._melspectrogram_session: object | None = None
        self._embedding_session: object | None = None
        self._classifier_session: object | None = None
        self._classifier_input_name = ""
        self._classifier_context_frames = 0
        self._state = WakeWordOperationalState.UNLOADED
        self._model_loading_seconds = 0.0
        self._inference_seconds = 0.0
        self._inference_count = 0
        self._audio_frames_processed = 0
        self._expected_start_frame = 0
        self._initialize_buffers()

    @property
    def state(self) -> WakeWordOperationalState:
        return self._state

    @property
    def available(self) -> bool:
        try:
            self._backend_loader()
        except WakeWordBackendUnavailableError:
            return False
        return True

    @property
    def model_identifier(self) -> str:
        return self._settings.model_identifier

    @property
    def metrics(self) -> WakeWordMetrics:
        return WakeWordMetrics(
            backend=self._settings.backend,
            model_identifier=self._settings.model_identifier,
            audio_frames_processed=self._audio_frames_processed,
            inference_count=self._inference_count,
            warmup_frames=min(self._inference_count, self._settings.warmup_frames),
            model_loading_seconds=self._model_loading_seconds,
            inference_seconds=self._inference_seconds,
        )

    def load(self) -> None:
        self._reserve()
        try:
            self._ensure_open()
            self._load_unlocked()
        finally:
            self._operation_lock.release()

    def evaluate(self, window: WakeWordWindow) -> WakeWordResult:
        self._reserve()
        try:
            self._ensure_open()
            if self._state is WakeWordOperationalState.FAILED:
                raise WakeWordError("Wake-word detector failed; reset is required")
            if window.start_frame != self._expected_start_frame:
                raise InvalidWakeWordInputError(
                    "Wake-word window timeline is discontinuous; reset is required"
                )
            if self._classifier_session is None:
                self._load_unlocked()
            return self._evaluate_unlocked(window)
        finally:
            self._operation_lock.release()

    def reset(self) -> None:
        self._reserve()
        try:
            self._ensure_open()
            self._initialize_buffers()
            self._expected_start_frame = 0
            self._inference_seconds = 0.0
            self._inference_count = 0
            self._audio_frames_processed = 0
            self._state = (
                WakeWordOperationalState.WARMING_UP
                if self._classifier_session is not None
                else WakeWordOperationalState.UNLOADED
            )
        finally:
            self._operation_lock.release()

    def close(self) -> None:
        self._reserve()
        try:
            self._melspectrogram_session = None
            self._embedding_session = None
            self._classifier_session = None
            self._numpy = None
            self._initialize_buffers()
            self._state = WakeWordOperationalState.CLOSED
        finally:
            self._operation_lock.release()

    def _reserve(self) -> None:
        if not self._operation_lock.acquire(blocking=False):
            raise WakeWordBusyError("Wake-word detector already has an active operation")

    def _ensure_open(self) -> None:
        if self._state is WakeWordOperationalState.CLOSED:
            raise WakeWordError("Wake-word detector is closed")

    def _load_unlocked(self) -> None:
        if self._classifier_session is not None:
            return
        if not self._settings.enabled:
            raise WakeWordDisabledError(
                "Wake-word detection is disabled; set KOSMOS_WAKEWORD_ENABLED=true"
            )
        model = self._settings.validate_model()
        numpy, onnxruntime = self._backend_loader()
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        started = self._clock()
        try:
            melspectrogram = onnxruntime.InferenceSession(
                str(model.melspectrogram_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            embedding = onnxruntime.InferenceSession(
                str(model.embedding_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            classifier = onnxruntime.InferenceSession(
                str(model.classifier_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            classifier_name, context_frames = self._validate_contracts(
                melspectrogram, embedding, classifier
            )
        except (InvalidWakeWordModelError, WakeWordBackendUnavailableError):
            raise
        except Exception as error:
            raise WakeWordBackendUnavailableError(
                "Local wake-word ONNX pipeline could not be loaded"
            ) from error
        self._numpy = numpy
        self._melspectrogram_session = melspectrogram
        self._embedding_session = embedding
        self._classifier_session = classifier
        self._classifier_input_name = classifier_name
        self._classifier_context_frames = context_frames
        self._initialize_buffers()
        self._model_loading_seconds = self._clock() - started
        self._state = WakeWordOperationalState.WARMING_UP

    def _validate_contracts(
        self, melspectrogram: object, embedding: object, classifier: object
    ) -> tuple[str, int]:
        self._validate_cpu_session(melspectrogram, "melspectrogram")
        self._validate_cpu_session(embedding, "embedding")
        self._validate_cpu_session(classifier, "classifier")
        mel_input, mel_output = self._single_io(melspectrogram, "melspectrogram")
        embedding_input, embedding_output = self._single_io(embedding, "embedding")
        classifier_input, classifier_output = self._single_io(classifier, "classifier")
        if (
            getattr(mel_input, "type", None) != "tensor(float)"
            or getattr(mel_output, "type", None) != "tensor(float)"
        ):
            raise InvalidWakeWordModelError("Melspectrogram tensor types are incompatible")
        mel_output_shape = getattr(mel_output, "shape", None)
        if mel_input.name != "input" or not isinstance(mel_output_shape, list):
            raise InvalidWakeWordModelError("Melspectrogram tensor contract is incompatible")
        if mel_output_shape[-1:] != [MELSPECTROGRAM_BINS]:
            raise InvalidWakeWordModelError("Melspectrogram output width is incompatible")
        embedding_input_shape = getattr(embedding_input, "shape", None)
        embedding_output_shape = getattr(embedding_output, "shape", None)
        classifier_output_shape = getattr(classifier_output, "shape", None)
        if embedding_input.name != "input_1" or not isinstance(embedding_input_shape, list):
            raise InvalidWakeWordModelError("Embedding tensor contract is incompatible")
        if embedding_input_shape[-3:] != [
            76,
            32,
            1,
        ]:
            raise InvalidWakeWordModelError("Embedding input shape is incompatible")
        if not isinstance(embedding_output_shape, list) or embedding_output_shape[-1:] != [
            EMBEDDING_SIZE
        ]:
            raise InvalidWakeWordModelError("Embedding output width is incompatible")
        classifier_shape = getattr(classifier_input, "shape", None)
        if not isinstance(classifier_shape, list) or len(classifier_shape) != 3:
            raise InvalidWakeWordModelError("Classifier input rank is incompatible")
        context_frames = classifier_shape[1]
        if (
            isinstance(context_frames, bool)
            or not isinstance(context_frames, int)
            or context_frames <= 0
        ):
            raise InvalidWakeWordModelError("Classifier context length must be fixed and positive")
        if classifier_shape[2] != EMBEDDING_SIZE:
            raise InvalidWakeWordModelError("Classifier embedding width is incompatible")
        if classifier_output_shape != [1, 1]:
            raise InvalidWakeWordModelError("Classifier must return one score")
        if any(
            getattr(item, "type", None) != "tensor(float)"
            for item in (embedding_input, embedding_output, classifier_input, classifier_output)
        ):
            raise InvalidWakeWordModelError("Wake-word tensor types must be float32")
        return classifier_input.name, context_frames

    @staticmethod
    def _validate_cpu_session(session: object, label: str) -> None:
        if session.get_providers() != ["CPUExecutionProvider"]:
            raise InvalidWakeWordModelError(f"{label.capitalize()} session must use only CPU")

    @staticmethod
    def _single_io(session: object, label: str) -> tuple[object, object]:
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise InvalidWakeWordModelError(f"{label.capitalize()} tensor contract is incompatible")
        return inputs[0], outputs[0]

    def _initialize_buffers(self) -> None:
        self._raw_buffer: deque[int] = deque(maxlen=RAW_BUFFER_SAMPLES)
        self._melspectrogram_buffer: object | None = None
        self._feature_buffer: object | None = None

    def _evaluate_unlocked(self, window: WakeWordWindow) -> WakeWordResult:
        assert self._numpy is not None
        assert self._melspectrogram_session is not None
        assert self._embedding_session is not None
        assert self._classifier_session is not None
        numpy = self._numpy
        started = self._clock()
        try:
            samples = numpy.frombuffer(window.audio.data, dtype="<i2")
            self._raw_buffer.extend(samples.tolist())
            mel_input = numpy.asarray(
                list(self._raw_buffer)[
                    -window.audio.frame_count - MELSPECTROGRAM_CONTEXT_SAMPLES :
                ],
                dtype=numpy.float32,
            )[None, :]
            mel_output = self._melspectrogram_session.run(None, {"input": mel_input})[0]
            melspectrogram = numpy.squeeze(numpy.asarray(mel_output, dtype=numpy.float32)) / 10 + 2
            self._append_melspectrogram(melspectrogram)
            embedding_input = self._melspectrogram_buffer[-MELSPECTROGRAM_CONTEXT_FRAMES:][
                None, :, :, None
            ].astype(numpy.float32)
            embedding_output = self._embedding_session.run(None, {"input_1": embedding_input})[0]
            embedding = numpy.squeeze(numpy.asarray(embedding_output, dtype=numpy.float32))
            self._append_embedding(embedding)
            classifier_input = self._feature_buffer[-self._classifier_context_frames :][
                None, :, :
            ].astype(numpy.float32)
            score_output = self._classifier_session.run(
                None, {self._classifier_input_name: classifier_input}
            )[0]
            score = self._validate_score(score_output)
        except InvalidWakeWordResultError:
            self._state = WakeWordOperationalState.FAILED
            raise
        except Exception as error:
            self._state = WakeWordOperationalState.FAILED
            raise WakeWordError("Wake-word ONNX inference failed; reset is required") from error
        inference_seconds = self._clock() - started
        ready = self._inference_count >= self._settings.warmup_frames
        self._inference_count += 1
        self._audio_frames_processed += window.audio.frame_count
        self._inference_seconds += inference_seconds
        self._expected_start_frame = window.end_frame
        self._state = (
            WakeWordOperationalState.READY if ready else WakeWordOperationalState.WARMING_UP
        )
        return WakeWordResult(
            score=score,
            start_frame=window.start_frame,
            end_frame=window.end_frame,
            inference_seconds=inference_seconds,
            ready=ready,
        )

    def _append_melspectrogram(self, value: object) -> None:
        assert self._numpy is not None
        numpy = self._numpy
        if (
            value.ndim != 2
            or value.shape[1] != MELSPECTROGRAM_BINS
            or not numpy.isfinite(value).all()
        ):
            raise InvalidWakeWordResultError("Melspectrogram output is invalid")
        if self._melspectrogram_buffer is None:
            self._melspectrogram_buffer = numpy.ones(
                (MELSPECTROGRAM_CONTEXT_FRAMES, MELSPECTROGRAM_BINS), dtype=numpy.float32
            )
        self._melspectrogram_buffer = numpy.vstack((self._melspectrogram_buffer, value))[
            -MELSPECTROGRAM_BUFFER_FRAMES:
        ]

    def _append_embedding(self, value: object) -> None:
        assert self._numpy is not None
        numpy = self._numpy
        if value.shape != (EMBEDDING_SIZE,) or not numpy.isfinite(value).all():
            raise InvalidWakeWordResultError("Embedding output is invalid")
        if self._feature_buffer is None:
            initial_frames = max(self._classifier_context_frames - 1, 0)
            self._feature_buffer = numpy.zeros(
                (initial_frames, EMBEDDING_SIZE), dtype=numpy.float32
            )
        self._feature_buffer = numpy.vstack((self._feature_buffer, value))[
            -EMBEDDING_BUFFER_FRAMES:
        ]

    def _validate_score(self, value: object) -> float:
        assert self._numpy is not None
        array = self._numpy.asarray(value)
        if array.shape != (1, 1):
            raise InvalidWakeWordResultError("Classifier score tensor shape is invalid")
        score = float(array[0, 0])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise InvalidWakeWordResultError("Classifier returned an invalid wake-word score")
        return score


def backend_available() -> bool:
    """Report optional runtime availability without reading model files."""

    try:
        load_onnx_backend()
    except WakeWordBackendUnavailableError:
        return False
    return True
