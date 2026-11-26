"""Local Ollama HTTP adapter for complete and streaming text inference."""

import json
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from uuid import uuid4

import httpx

from kosmos.core.config import ApplicationSettings
from kosmos.core.exceptions import (
    InferenceError,
    InvalidProviderResponseError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
)
from kosmos.intelligence.tools.models import (
    ToolCall,
    ToolInferenceRequest,
    ToolInferenceResponse,
    ToolMessage,
    ToolMessageRole,
    thaw_json,
)

_LOGGER = logging.getLogger("kosmos.intelligence.providers.ollama")
_CHAT_ENDPOINT = "/api/chat"
_TAGS_ENDPOINT = "/api/tags"
_VERSION_ENDPOINT = "/api/version"
_METRIC_FIELDS = {
    "total_duration": "total_duration_ns",
    "load_duration": "load_duration_ns",
    "prompt_eval_count": "prompt_eval_count",
    "prompt_eval_duration": "prompt_eval_duration_ns",
    "eval_count": "eval_count",
    "eval_duration": "eval_duration_ns",
}
_MAX_TOOL_CALLS = 8
_MAX_TOOL_ARGUMENT_BYTES = 8_192


@dataclass(frozen=True, slots=True)
class OllamaModel:
    """Validated metadata for one model installed in the local Ollama service."""

    name: str
    model: str
    modified_at: str
    size: int
    digest: str


class OllamaProvider:
    """Own and reuse one secure asynchronous client for the local Ollama API."""

    def __init__(
        self,
        settings: ApplicationSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not isinstance(settings, ApplicationSettings):
            raise TypeError("settings must be ApplicationSettings")

        timeout = httpx.Timeout(settings.ollama_timeout_seconds)
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=timeout,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        )
        self._closed = False

    @property
    def is_closed(self) -> bool:
        """Report whether this provider has released its HTTP client."""

        return self._closed

    async def __aenter__(self) -> "OllamaProvider":
        self._ensure_open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the owned client; repeated calls are safe."""

        if self._closed:
            return

        await self._client.aclose()
        self._closed = True

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate and validate one complete textual response."""

        self._ensure_open()
        payload = self._build_chat_payload(request, stream=False)

        response = await self._request("POST", _CHAT_ENDPOINT, json_payload=payload)
        document = self._decode_document(response)
        self._raise_embedded_error(document)

        if document.get("done") is not True:
            raise InvalidProviderResponseError("Ollama returned an incomplete response")

        model = _require_non_empty_string(document, "model")
        message = _require_mapping(document, "message")

        if message.get("role") != "assistant":
            raise InvalidProviderResponseError("Ollama response message has an invalid role")

        content = _require_string(message, "content")

        if not content.strip():
            raise InvalidProviderResponseError("Ollama returned an empty response")

        return InferenceResponse(
            model=model,
            content=content,
            metrics=_parse_metrics(document),
        )

    async def generate_with_tools(self, request: ToolInferenceRequest) -> ToolInferenceResponse:
        """Generate structured tool proposals without authorizing or executing them."""

        self._ensure_open()
        payload = self._build_tool_chat_payload(request)

        response = await self._request("POST", _CHAT_ENDPOINT, json_payload=payload)
        document = self._decode_document(response)
        self._raise_embedded_error(document)

        if document.get("done") is not True:
            raise InvalidProviderResponseError("Ollama returned an incomplete response")

        model = _require_non_empty_string(document, "model")
        message = _require_mapping(document, "message")

        if message.get("role") != "assistant":
            raise InvalidProviderResponseError("Ollama response message has an invalid role")

        content = _require_string(message, "content")
        calls = _parse_tool_calls(message)

        if not content.strip() and not calls:
            raise InvalidProviderResponseError("Ollama returned an empty response")

        return ToolInferenceResponse(
            model=model,
            content=content,
            tool_calls=calls,
            metrics=_parse_metrics(document),
        )

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        """Yield NDJSON events incrementally until Ollama reports completion."""

        self._ensure_open()
        payload = self._build_chat_payload(request, stream=True)
        completed = False

        try:
            async with self._client.stream("POST", _CHAT_ENDPOINT, json=payload) as response:
                self._raise_for_status(response)

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    document = _decode_json_object(line)
                    self._raise_embedded_error(document)
                    chunk = _parse_stream_chunk(document)

                    yield chunk

                    if chunk.done:
                        completed = True
                        break
        except httpx.TimeoutException as error:
            _LOGGER.warning("Ollama streaming timed out")
            raise ProviderTimeoutError("Ollama streaming timed out") from error
        except httpx.RequestError as error:
            _LOGGER.warning("Ollama streaming connection failed")
            raise ProviderUnavailableError("Ollama streaming connection failed") from error

        if not completed:
            raise InvalidProviderResponseError("Ollama stream ended before completion")

    async def is_available(self) -> bool:
        """Return false only when the local service cannot be reached.

        Timeouts, HTTP failures, and invalid responses remain distinct exceptions.
        """

        try:
            await self.get_version()
        except ProviderUnavailableError:
            return False

        return True

    async def get_version(self) -> str:
        """Return the validated Ollama service version string."""

        self._ensure_open()
        response = await self._request("GET", _VERSION_ENDPOINT)
        document = self._decode_document(response)
        self._raise_embedded_error(document)

        return _require_non_empty_string(document, "version")

    async def list_models(self) -> tuple[OllamaModel, ...]:
        """Return validated installed-model metadata; an empty tuple is valid."""

        self._ensure_open()
        response = await self._request("GET", _TAGS_ENDPOINT)
        document = self._decode_document(response)
        self._raise_embedded_error(document)
        models = document.get("models")

        if not isinstance(models, list):
            raise InvalidProviderResponseError("Ollama model list is invalid")

        return tuple(_parse_model(item) for item in models)

    def _build_chat_payload(self, request: InferenceRequest, *, stream: bool) -> dict[str, object]:
        if not isinstance(request, InferenceRequest):
            raise TypeError("request must be InferenceRequest")

        thinking = self._settings.ollama_thinking if request.thinking is None else request.thinking

        return {
            "model": request.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "stream": stream,
            "think": thinking,
            "keep_alive": self._settings.ollama_keep_alive,
            "options": {"num_ctx": self._settings.ollama_context_length},
        }

    def _build_tool_chat_payload(self, request: ToolInferenceRequest) -> dict[str, object]:
        if not isinstance(request, ToolInferenceRequest):
            raise TypeError("request must be a ToolInferenceRequest")

        thinking = self._settings.ollama_thinking if request.thinking is None else request.thinking

        return {
            "model": request.model,
            "messages": [_serialize_tool_message(message) for message in request.messages],
            "tools": [definition.to_provider_schema() for definition in request.tools],
            "stream": False,
            "think": thinking,
            "keep_alive": self._settings.ollama_keep_alive,
            "options": {"num_ctx": self._settings.ollama_context_length},
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_payload: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, endpoint, json=json_payload)
        except httpx.TimeoutException as error:
            _LOGGER.warning("Ollama request timed out")
            raise ProviderTimeoutError("Ollama request timed out") from error
        except httpx.RequestError as error:
            _LOGGER.warning("Ollama connection failed")
            raise ProviderUnavailableError("Ollama connection failed") from error

        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return

        _LOGGER.warning("Ollama returned HTTP status %d", response.status_code)
        raise ProviderHTTPError(
            f"Ollama request failed with HTTP {response.status_code}",
            response.status_code,
        )

    @staticmethod
    def _decode_document(response: httpx.Response) -> dict[str, object]:
        try:
            document = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InvalidProviderResponseError("Ollama returned invalid JSON") from error

        if not isinstance(document, dict):
            raise InvalidProviderResponseError("Ollama returned an invalid JSON document")

        return document

    @staticmethod
    def _raise_embedded_error(document: Mapping[str, object]) -> None:
        if "error" not in document:
            return

        error = document["error"]

        if not isinstance(error, str) or not error.strip():
            raise InvalidProviderResponseError("Ollama returned an invalid error response")

        raise InferenceError("Ollama reported an inference failure")

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("OllamaProvider is closed")


def _decode_json_object(line: str) -> dict[str, object]:
    try:
        document = json.loads(line)
    except json.JSONDecodeError as error:
        raise InvalidProviderResponseError("Ollama stream contained invalid JSON") from error

    if not isinstance(document, dict):
        raise InvalidProviderResponseError("Ollama stream contained an invalid JSON document")

    return document


def _parse_stream_chunk(document: Mapping[str, object]) -> InferenceChunk:
    model = _require_non_empty_string(document, "model")
    message = _require_mapping(document, "message")
    content = _require_string(message, "content")
    done = document.get("done")

    if not isinstance(done, bool):
        raise InvalidProviderResponseError("Ollama stream event has an invalid done field")

    return InferenceChunk(
        model=model,
        content=content,
        done=done,
        metrics=_parse_metrics(document) if done else None,
    )


def _serialize_tool_message(message: ToolMessage) -> dict[str, object]:
    serialized: dict[str, object] = {
        "role": message.role.value,
        "content": message.content,
    }

    if message.role is ToolMessageRole.TOOL:
        serialized["tool_name"] = message.tool_name

    if message.tool_calls:
        serialized["tool_calls"] = [
            {
                "function": {
                    "name": call.name,
                    "arguments": thaw_json(call.arguments),
                }
            }
            for call in message.tool_calls
        ]

    return serialized


def _parse_tool_calls(message: Mapping[str, object]) -> tuple[ToolCall, ...]:
    raw_calls = message.get("tool_calls", [])

    if not isinstance(raw_calls, list):
        raise InvalidProviderResponseError("Ollama tool_calls must be an array")
    if len(raw_calls) > _MAX_TOOL_CALLS:
        raise InvalidProviderResponseError("Ollama returned too many tool calls")

    calls: list[ToolCall] = []

    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            raise InvalidProviderResponseError("Ollama tool call must be an object")

        function = _require_mapping(raw_call, "function")
        name = _require_non_empty_string(function, "name")
        arguments = function.get("arguments")

        if not isinstance(arguments, dict):
            raise InvalidProviderResponseError("Ollama tool arguments must be an object")

        try:
            encoded = json.dumps(
                arguments,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise InvalidProviderResponseError("Ollama tool arguments are invalid") from error

        if len(encoded.encode("utf-8")) > _MAX_TOOL_ARGUMENT_BYTES:
            raise InvalidProviderResponseError("Ollama tool arguments exceed the size limit")

        try:
            call = ToolCall(f"tool_call_{uuid4().hex}", name, arguments)
        except (TypeError, ValueError) as error:
            raise InvalidProviderResponseError("Ollama tool call is invalid") from error

        calls.append(call)

    return tuple(calls)


def _parse_metrics(document: Mapping[str, object]) -> InferenceMetrics | None:
    values: dict[str, int | None] = {}
    present = False

    for source_name, target_name in _METRIC_FIELDS.items():
        value = document.get(source_name)

        if value is None:
            values[target_name] = None
            continue

        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvalidProviderResponseError(f"Ollama metric {source_name} is invalid")

        values[target_name] = value
        present = True

    return InferenceMetrics(**values) if present else None


def _parse_model(value: object) -> OllamaModel:
    if not isinstance(value, dict):
        raise InvalidProviderResponseError("Ollama model entry is invalid")

    size = value.get("size")

    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise InvalidProviderResponseError("Ollama model size is invalid")

    return OllamaModel(
        name=_require_non_empty_string(value, "name"),
        model=_require_non_empty_string(value, "model"),
        modified_at=_require_non_empty_string(value, "modified_at"),
        size=size,
        digest=_require_non_empty_string(value, "digest"),
    )


def _require_mapping(document: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = document.get(field_name)

    if not isinstance(value, dict):
        raise InvalidProviderResponseError(f"Ollama field {field_name} must be an object")

    return value


def _require_string(document: Mapping[str, object], field_name: str) -> str:
    value = document.get(field_name)

    if not isinstance(value, str):
        raise InvalidProviderResponseError(f"Ollama field {field_name} must be a string")

    return value


def _require_non_empty_string(document: Mapping[str, object], field_name: str) -> str:
    value = _require_string(document, field_name)

    if not value.strip():
        raise InvalidProviderResponseError(f"Ollama field {field_name} must not be empty")

    return value
