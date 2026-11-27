"""Controlled asynchronous adapter for an independently installed Piper CLI."""

import asyncio
import shutil
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import (
    InvalidSynthesizedAudioError,
    InvalidVoiceConfigurationError,
    SpeechSynthesisError,
    SynthesisTimeoutError,
    TTSBackendUnavailableError,
)
from kosmos.voice.tts.config import TTSSettings
from kosmos.voice.tts.models import (
    SpeechSynthesisMetrics,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
)
from kosmos.voice.tts.text import segment_text

ProcessFactory = Callable[..., Awaitable[asyncio.subprocess.Process]]


class PiperExternalProcessSynthesizer:
    """Run one bounded Piper process per request and return raw mono PCM."""

    def __init__(
        self,
        settings: TTSSettings,
        *,
        process_factory: ProcessFactory = asyncio.create_subprocess_exec,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._process_factory = process_factory
        self._clock = clock
        self._active_process: asyncio.subprocess.Process | None = None
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def backend(self) -> str:
        return "piper"

    def is_available(self) -> bool:
        """Report executable and voice-file presence without starting a process."""

        try:
            self._resolve_executable()
            self._settings.load_voice_metadata()
        except SpeechSynthesisError:
            return False

        return True

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        """Synthesize prepared text through stdin with bounded stdout and stderr."""

        if self._closed:
            raise TTSBackendUnavailableError("Piper synthesizer is closed")
        if not self._settings.enabled:
            raise TTSBackendUnavailableError(
                "Text-to-speech is disabled; set KOSMOS_TTS_ENABLED=true explicitly"
            )
        if request.voice.identifier != self._settings.voice_identifier:
            raise InvalidVoiceConfigurationError("Requested voice is not configured")

        executable = self._resolve_executable()
        metadata = self._settings.load_voice_metadata()
        segments = segment_text(request.text)
        command = self._build_arguments(executable, request)
        payload = ("\n".join(segments) + "\n").encode("utf-8")

        async with self._lock:
            started = self._clock()
            process = await self._start_process(command)
            self._active_process = process
            try:
                stdout, _stderr = await asyncio.wait_for(
                    self._exchange(process, payload),
                    timeout=self._settings.timeout_seconds,
                )
            except TimeoutError as error:
                await self._terminate(process)
                raise SynthesisTimeoutError(
                    f"Piper exceeded the {self._settings.timeout_seconds:g}-second timeout"
                ) from error
            except asyncio.CancelledError:
                await self._terminate(process)
                raise
            except Exception:
                await self._terminate(process)
                raise
            finally:
                self._active_process = None

            elapsed = self._clock() - started

        if process.returncode != 0:
            raise SpeechSynthesisError("Piper exited without completing synthesis")
        if not stdout:
            raise InvalidSynthesizedAudioError("Piper returned empty raw audio")
        if len(stdout) % metadata.audio_format.bytes_per_frame:
            raise InvalidSynthesizedAudioError("Piper returned partial PCM frames")

        audio = AudioChunk(stdout, metadata.audio_format)
        if audio.duration_seconds <= 0 or elapsed <= 0:
            raise InvalidSynthesizedAudioError("Piper returned invalid synthesis timing")
        metrics = SpeechSynthesisMetrics(
            backend=self.backend,
            voice_identifier=request.voice.identifier,
            text_characters=len(request.text),
            process_duration_seconds=elapsed,
            audio_duration_seconds=audio.duration_seconds,
            sample_rate=audio.format.sample_rate,
            audio_frames=audio.frame_count,
            audio_bytes=len(audio.data),
        )
        return SpeechSynthesisResult(audio, metrics)

    async def close(self) -> None:
        """Prevent later requests and terminate an active child process."""

        self._closed = True
        if self._active_process is not None:
            await self._terminate(self._active_process)

    def _resolve_executable(self) -> str:
        configured = self._settings.executable
        if configured is None:
            raise TTSBackendUnavailableError("Piper executable path is not configured")
        if configured.suffix.lower() in {".bat", ".cmd"}:
            raise TTSBackendUnavailableError("Piper batch and command scripts are not allowed")

        value = str(configured)
        resolved = shutil.which(value)
        if resolved is None and configured.is_file():
            resolved = str(configured.resolve())
        if resolved is None:
            raise TTSBackendUnavailableError("Configured Piper executable is unavailable")

        return resolved

    def _build_arguments(self, executable: str, request: SpeechSynthesisRequest) -> tuple[str, ...]:
        model_path = self._settings.model_path
        config_path = self._settings.config_path
        if model_path is None or config_path is None:
            raise InvalidVoiceConfigurationError("Piper model and config paths must be configured")

        return (
            executable,
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--output-raw",
            "--length-scale",
            str(request.settings.length_scale),
            "--volume",
            str(request.settings.volume),
        )

    async def _start_process(self, command: tuple[str, ...]) -> asyncio.subprocess.Process:
        try:
            return await self._process_factory(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, PermissionError) as error:
            raise TTSBackendUnavailableError("Piper process could not start") from error

    async def _exchange(
        self, process: asyncio.subprocess.Process, payload: bytes
    ) -> tuple[bytes, bytes]:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise TTSBackendUnavailableError("Piper process pipes are unavailable")

        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()
        stdout_task = asyncio.create_task(
            _read_limited(
                process.stdout,
                self._settings.max_audio_bytes,
                InvalidSynthesizedAudioError("Piper audio exceeded the configured byte limit"),
            )
        )
        stderr_task = asyncio.create_task(
            _read_limited(
                process.stderr,
                self._settings.max_stderr_bytes,
                SpeechSynthesisError("Piper stderr exceeded the configured byte limit"),
            )
        )
        try:
            stdout, stderr, _return_code = await asyncio.gather(
                stdout_task, stderr_task, process.wait()
            )
        except BaseException:
            stdout_task.cancel()
            stderr_task.cancel()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise

        return stdout, stderr

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.kill()
        with suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=5.0)


async def _read_limited(stream: asyncio.StreamReader, limit: int, error: Exception) -> bytes:
    data = bytearray()
    while block := await stream.read(min(64 * 1024, limit - len(data) + 1)):
        data.extend(block)
        if len(data) > limit:
            raise error

    return bytes(data)
