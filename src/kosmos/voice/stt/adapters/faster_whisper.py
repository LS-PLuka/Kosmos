"""Lazy, local-only Faster Whisper speech recognition adapter."""

import asyncio
import math
from collections.abc import Callable, Iterable
from contextlib import suppress
from importlib import import_module
from time import monotonic
from typing import Protocol, cast

from kosmos.voice.audio.models import SampleFormat
from kosmos.voice.exceptions import (
    InvalidRecognitionRequestError,
    InvalidTranscriptionResultError,
    SpeechRecognitionBusyError,
    SpeechRecognitionDisabledError,
    SpeechRecognitionError,
    STTBackendUnavailableError,
)
from kosmos.voice.stt.config import STTSettings
from kosmos.voice.stt.models import (
    MAX_SEGMENTS,
    MAX_TRANSCRIPT_CHARACTERS,
    SpeechRecognitionMetrics,
    SpeechRecognitionRequest,
    SpeechRecognitionResult,
    SpeechRecognitionStatus,
    TranscriptionSegment,
)


class _Model(Protocol):
    def transcribe(self, audio: object, **options: object) -> tuple[Iterable[object], object]: ...


BackendLoader = Callable[[], tuple[Callable[..., _Model], Callable[[bytes], object]]]


def load_faster_whisper_backend() -> tuple[Callable[..., _Model], Callable[[bytes], object]]:
    """Import Faster Whisper and NumPy only for explicit model work."""

    try:
        faster_whisper = import_module("faster_whisper")
        numpy = import_module("numpy")
    except ModuleNotFoundError as error:
        if error.name in {"faster_whisper", "numpy"}:
            raise STTBackendUnavailableError(
                "Speech recognition support is not installed; install the 'stt' extra"
            ) from error
        raise STTBackendUnavailableError(
            "Faster Whisper could not load one of its runtime dependencies"
        ) from error
    except (ImportError, OSError) as error:
        raise STTBackendUnavailableError(
            "Faster Whisper is installed, but a native runtime dependency is unavailable"
        ) from error

    def convert(data: bytes) -> object:
        samples = numpy.frombuffer(data, dtype="<i2")
        return samples.astype(numpy.float32) / 32768.0

    return cast(Callable[..., _Model], faster_whisper.WhisperModel), convert


class FasterWhisperRecognizer:
    """Recognize bounded PCM using one reusable local CPU model."""

    def __init__(
        self,
        settings: STTSettings,
        *,
        backend_loader: BackendLoader = load_faster_whisper_backend,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings
        self._backend_loader = backend_loader
        self._clock = clock
        self._model: _Model | None = None
        self._convert: Callable[[bytes], object] | None = None
        self._busy = False
        self._closed = False

    @property
    def backend(self) -> str:
        return self._settings.backend

    def is_available(self) -> bool:
        try:
            self._settings.validate_model()
            self._backend_loader()
        except SpeechRecognitionError:
            return False
        return True

    async def load(self) -> None:
        await self._run_native(self._load_sync)

    async def recognize(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult:
        self._validate_request(request)
        result = await self._run_native(lambda: self._recognize_sync(request))
        return cast(SpeechRecognitionResult, result)

    async def close(self) -> None:
        if self._busy:
            raise SpeechRecognitionBusyError("Speech recognizer is still processing native work")
        self._model = None
        self._convert = None
        self._closed = True

    async def _run_native(self, operation: Callable[[], object]) -> object:
        if self._closed:
            raise SpeechRecognitionError("Speech recognizer is closed")
        if self._busy:
            raise SpeechRecognitionBusyError("Speech recognizer already has an active operation")

        self._busy = True
        task = asyncio.create_task(asyncio.to_thread(operation))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            task.add_done_callback(self._release_after_cancel)
            raise
        finally:
            if task.done():
                self._busy = False

    def _release_after_cancel(self, task: asyncio.Task[object]) -> None:
        self._busy = False
        with suppress(Exception):
            task.result()

    def _load_sync(self) -> float:
        if self._model is not None:
            return 0.0

        metadata = self._settings.validate_model()
        model_factory, converter = self._backend_loader()
        started = self._clock()
        try:
            model = model_factory(
                model_size_or_path=str(metadata.path),
                device="cpu",
                compute_type="int8",
                cpu_threads=self._settings.cpu_threads,
                num_workers=1,
                local_files_only=True,
            )
        except SpeechRecognitionError:
            raise
        except Exception as error:
            raise STTBackendUnavailableError(
                "Local Faster Whisper model could not be loaded"
            ) from error

        self._model = model
        self._convert = converter
        return self._clock() - started

    def _recognize_sync(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult:
        operation_started = self._clock()
        model_reused = self._model is not None
        loading_seconds = self._load_sync()
        assert self._model is not None and self._convert is not None

        waveform = self._convert(request.audio.data)
        recognition_started = self._clock()
        try:
            native_segments, _info = self._model.transcribe(
                waveform,
                language=self._settings.language,
                task="transcribe",
                beam_size=self._settings.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
                word_timestamps=False,
            )
            segments = self._materialize(native_segments)
        except InvalidTranscriptionResultError:
            raise
        except Exception as error:
            raise SpeechRecognitionError("Faster Whisper recognition failed") from error
        recognition_seconds = self._clock() - recognition_started

        text = "".join(segment.text for segment in segments).strip()
        if len(text) > MAX_TRANSCRIPT_CHARACTERS:
            raise InvalidTranscriptionResultError("Transcript exceeds the character limit")
        if not text:
            segments = ()
            status = SpeechRecognitionStatus.NO_TRANSCRIPTION
        else:
            status = SpeechRecognitionStatus.TRANSCRIBED

        metrics = SpeechRecognitionMetrics(
            backend=self.backend,
            model_identifier=self._settings.model_identifier,
            device="cpu",
            compute_type="int8",
            configured_language=self._settings.language,
            audio_duration_seconds=request.audio.duration_seconds,
            audio_frames=request.audio.frame_count,
            audio_bytes=len(request.audio.data),
            model_loading_seconds=loading_seconds,
            recognition_seconds=recognition_seconds,
            total_seconds=self._clock() - operation_started,
            segment_count=len(segments),
            transcript_characters=len(text),
            model_reused=model_reused,
        )
        return SpeechRecognitionResult(status, text, self._settings.language, segments, metrics)

    def _validate_request(self, request: SpeechRecognitionRequest) -> None:
        if not self._settings.enabled:
            raise SpeechRecognitionDisabledError(
                "Speech recognition is disabled; set KOSMOS_STT_ENABLED=true explicitly"
            )
        audio = request.audio
        if audio.format.sample_rate != 16_000 or audio.format.channels != 1:
            raise InvalidRecognitionRequestError("STT requires mono PCM at 16000 Hz")
        if audio.format.sample_format is not SampleFormat.SIGNED_16_LE:
            raise InvalidRecognitionRequestError("STT requires signed 16-bit little-endian PCM")
        if audio.duration_seconds > self._settings.max_audio_seconds:
            raise InvalidRecognitionRequestError(
                "Recognition audio exceeds the configured duration limit"
            )
        if not any(audio.data):
            raise InvalidRecognitionRequestError("Recognition audio contains only zero-valued PCM")

    def _materialize(self, native_segments: Iterable[object]) -> tuple[TranscriptionSegment, ...]:
        segments = []
        for native in native_segments:
            if len(segments) >= MAX_SEGMENTS:
                raise InvalidTranscriptionResultError("Transcription exceeds the segment limit")
            try:
                segment = TranscriptionSegment(
                    start_seconds=float(native.start),
                    end_seconds=float(native.end),
                    text=str(native.text),
                    average_log_probability=float(native.avg_logprob),
                    no_speech_probability=float(native.no_speech_prob),
                )
            except (TypeError, ValueError, AttributeError) as error:
                raise InvalidTranscriptionResultError(
                    "Faster Whisper returned invalid segment metadata"
                ) from error
            timestamps = (segment.start_seconds, segment.end_seconds)
            if not all(math.isfinite(value) for value in timestamps):
                raise InvalidTranscriptionResultError("Segment timestamps must be finite")
            segments.append(segment)

        return tuple(segments)
