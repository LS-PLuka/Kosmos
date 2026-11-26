"""Behavioral tests for the local Ollama HTTP adapter."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from kosmos.core.config import ApplicationSettings
from kosmos.core.exceptions import (
    InferenceError,
    InvalidProviderResponseError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from kosmos.intelligence.models import InferenceChunk, InferenceRequest, Message, MessageRole
from kosmos.intelligence.providers.ollama import OllamaModel, OllamaProvider


def _request(*, thinking: bool | None = None) -> InferenceRequest:
    return InferenceRequest(
        "qwen-test",
        (
            Message(MessageRole.SYSTEM, "Be concise"),
            Message(MessageRole.USER, "Olá, Kosmos 🌌"),
            Message(MessageRole.ASSISTANT, "Ready"),
        ),
        thinking=thinking,
    )


def _complete_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "model": "qwen-test",
        "message": {"role": "assistant", "content": "Olá! 🌌"},
        "done": True,
        "total_duration": 100,
        "eval_count": 3,
    }
    document.update(overrides)
    return document


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    settings: ApplicationSettings | None = None,
) -> OllamaProvider:
    return OllamaProvider(settings or ApplicationSettings(), transport=httpx.MockTransport(handler))


def test_serializes_complete_request_and_preserves_messages() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_complete_document())

    settings = ApplicationSettings(
        ollama_context_length=8192,
        ollama_thinking=True,
        ollama_keep_alive="30s",
    )
    provider = _provider(handler, settings)

    response = asyncio.run(provider.generate(_request()))
    asyncio.run(provider.aclose())

    assert captured == {
        "model": "qwen-test",
        "messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Olá, Kosmos 🌌"},
            {"role": "assistant", "content": "Ready"},
        ],
        "stream": False,
        "think": True,
        "keep_alive": "30s",
        "options": {"num_ctx": 8192},
    }
    assert response.content == "Olá! 🌌"
    assert response.metrics is not None
    assert response.metrics.total_duration_ns == 100


def test_request_thinking_overrides_settings_without_mutation() -> None:
    captured: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content)["think"])
        return httpx.Response(200, json=_complete_document())

    settings = ApplicationSettings(ollama_thinking=True)
    provider = _provider(handler, settings)

    asyncio.run(provider.generate(_request(thinking=False)))
    asyncio.run(provider.aclose())

    assert captured == [False]
    assert settings.ollama_thinking is True


def test_does_not_expose_thinking_as_response_content() -> None:
    document = _complete_document(
        message={"role": "assistant", "thinking": "private trace", "content": "Final answer"}
    )
    provider = _provider(lambda request: httpx.Response(200, json=document))

    response = asyncio.run(provider.generate(_request()))
    asyncio.run(provider.aclose())

    assert response.content == "Final answer"
    assert "private" not in response.content


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"model": "qwen-test", "message": {"role": "assistant", "content": "answer"}},
        _complete_document(message={"role": "assistant", "content": ""}),
        _complete_document(message={"role": "user", "content": "answer"}),
        _complete_document(total_duration="100"),
    ],
)
def test_rejects_empty_incomplete_or_invalid_complete_responses(
    document: dict[str, object],
) -> None:
    provider = _provider(lambda request: httpx.Response(200, json=document))

    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())


def test_rejects_invalid_complete_json() -> None:
    provider = _provider(lambda request: httpx.Response(200, content=b"not-json"))

    with pytest.raises(InvalidProviderResponseError, match="JSON"):
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())


@pytest.mark.parametrize("status_code", [300, 400, 404, 429, 500, 502])
def test_maps_unsuccessful_statuses_without_special_casing_404(status_code: int) -> None:
    provider = _provider(lambda request: httpx.Response(status_code, json={"error": "details"}))

    with pytest.raises(ProviderHTTPError) as captured:
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())
    assert captured.value.status_code == status_code


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectError("offline"), ProviderUnavailableError),
        (httpx.ReadTimeout("slow"), ProviderTimeoutError),
    ],
)
def test_maps_transport_failures(error: httpx.RequestError, expected: type[InferenceError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        error.request = request
        raise error

    provider = _provider(handler)

    with pytest.raises(expected):
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())


class _ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.requested = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.requested += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class _CancelledStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if False:
            yield b""

        raise asyncio.CancelledError

    async def aclose(self) -> None:
        self.closed = True


def _stream_response(stream: httpx.AsyncByteStream) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "application/x-ndjson"}, stream=stream)


def test_streams_ordered_fragments_and_final_metrics_across_transport_chunks() -> None:
    stream = _ChunkedStream(
        [
            b'{"model":"qwen-test","message":{"content":"Ol',
            'á 🌌"},"done":false}\n'.encode(),
            b'{"model":"qwen-test","message":{"content":" "},"done":false}\n',
            b'{"model":"qwen-test","message":{"content":"done"},"done":true,',
            b'"eval_count":2}\n',
        ]
    )
    provider = _provider(lambda request: _stream_response(stream))

    async def consume() -> list[InferenceChunk]:
        return [chunk async for chunk in provider.stream(_request())]

    chunks = asyncio.run(consume())
    asyncio.run(provider.aclose())

    assert [chunk.content for chunk in chunks] == ["Olá 🌌", " ", "done"]
    assert [chunk.done for chunk in chunks] == [False, False, True]
    assert chunks[-1].metrics is not None
    assert chunks[-1].metrics.eval_count == 2
    assert stream.closed is True


def test_delivers_first_chunk_before_reading_the_rest() -> None:
    stream = _ChunkedStream(
        [
            b'{"model":"qwen-test","message":{"content":"first"},"done":false}\n',
            b'{"model":"qwen-test","message":{"content":"last"},"done":true}\n',
        ]
    )
    provider = _provider(lambda request: _stream_response(stream))

    async def consume_first() -> None:
        iterator = provider.stream(_request())
        first = await anext(iterator)

        assert first.content == "first"
        assert stream.requested == 1

        await iterator.aclose()

    asyncio.run(consume_first())
    asyncio.run(provider.aclose())

    assert stream.closed is True


@pytest.mark.parametrize(
    "line",
    [
        b"not-json\n",
        b"[]\n",
        b'{"model":"qwen-test","message":{"content":1},"done":false}\n',
    ],
)
def test_rejects_invalid_stream_events(line: bytes) -> None:
    provider = _provider(lambda request: _stream_response(_ChunkedStream([line])))

    async def consume() -> None:
        async for _ in provider.stream(_request()):
            pass

    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(consume())

    asyncio.run(provider.aclose())


def test_detects_stream_error_and_premature_end() -> None:
    error_stream = _ChunkedStream([b'{"error":"private failure details"}\n'])
    provider = _provider(lambda request: _stream_response(error_stream))

    async def consume() -> None:
        async for _ in provider.stream(_request()):
            pass

    with pytest.raises(InferenceError, match="inference failure"):
        asyncio.run(consume())

    asyncio.run(provider.aclose())

    premature = _provider(
        lambda request: _stream_response(
            _ChunkedStream(
                [b'{"model":"qwen-test","message":{"content":"partial"},"done":false}\n']
            )
        )
    )

    with pytest.raises(InvalidProviderResponseError, match="before completion"):
        asyncio.run(_consume(premature))

    asyncio.run(premature.aclose())


async def _consume(provider: OllamaProvider) -> None:
    async for _ in provider.stream(_request()):
        pass


def test_accepts_empty_intermediate_and_final_events() -> None:
    stream = _ChunkedStream(
        [
            b'{"model":"qwen-test","message":{"content":"","thinking":"private"},"done":false}\n',
            b'{"model":"qwen-test","message":{"content":""},"done":true}\n',
        ]
    )
    provider = _provider(lambda request: _stream_response(stream))

    async def consume() -> list[InferenceChunk]:
        return [chunk async for chunk in provider.stream(_request())]

    chunks = asyncio.run(consume())
    asyncio.run(provider.aclose())

    assert [chunk.content for chunk in chunks] == ["", ""]
    assert chunks[-1].done is True


def test_stream_propagates_cancellation_and_releases_resources_without_tasks() -> None:
    stream = _CancelledStream()
    provider = _provider(lambda request: _stream_response(stream))

    async def cancel() -> None:
        tasks_before = asyncio.all_tasks()

        with pytest.raises(asyncio.CancelledError):
            await _consume(provider)

        assert asyncio.all_tasks() == tasks_before

    asyncio.run(cancel())
    asyncio.run(provider.aclose())

    assert stream.closed is True


def test_maps_stream_timeout_without_retrying() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow stream", request=request)

    provider = _provider(handler)

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(_consume(provider))

    asyncio.run(provider.aclose())
    assert calls == 1


def test_gets_version_and_lists_models_including_an_empty_list() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)

        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.18"})

        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen3.5:4b-q4_K_M",
                        "model": "qwen3.5:4b-q4_K_M",
                        "modified_at": "2026-01-01T00:00:00Z",
                        "size": 3_300_000_000,
                        "digest": "abc123",
                    }
                ]
            },
        )

    provider = _provider(handler)

    assert asyncio.run(provider.get_version()) == "0.40.18"
    assert asyncio.run(provider.is_available()) is True
    assert asyncio.run(provider.list_models()) == (
        OllamaModel(
            name="qwen3.5:4b-q4_K_M",
            model="qwen3.5:4b-q4_K_M",
            modified_at="2026-01-01T00:00:00Z",
            size=3_300_000_000,
            digest="abc123",
        ),
    )
    asyncio.run(provider.aclose())

    assert calls == ["/api/version", "/api/version", "/api/tags"]

    empty = _provider(lambda request: httpx.Response(200, json={"models": []}))
    assert asyncio.run(empty.list_models()) == ()
    asyncio.run(empty.aclose())


def test_availability_distinguishes_connection_timeout_and_invalid_response() -> None:
    unavailable = _provider(lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    assert asyncio.run(unavailable.is_available()) is False
    asyncio.run(unavailable.aclose())

    timed_out = _provider(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(timed_out.is_available())
    asyncio.run(timed_out.aclose())

    invalid = _provider(lambda request: httpx.Response(200, json={"version": 1}))
    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(invalid.is_available())
    asyncio.run(invalid.aclose())


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"models": {}},
        {"models": ["invalid"]},
        {"models": [{"name": "model", "model": "model", "size": -1}]},
    ],
)
def test_rejects_invalid_model_payloads(document: dict[str, object]) -> None:
    provider = _provider(lambda request: httpx.Response(200, json=document))

    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(provider.list_models())

    asyncio.run(provider.aclose())


def test_reuses_and_explicitly_closes_owned_client() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_complete_document())

    provider = _provider(handler)

    async def use_context() -> None:
        async with provider:
            await provider.generate(_request())
            await provider.generate(_request())

    asyncio.run(use_context())

    assert calls == 2
    assert provider.is_closed is True

    with pytest.raises(RuntimeError, match="closed"):
        asyncio.run(provider.generate(_request()))


def test_client_disables_environment_trust_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://example.com:8080")
    provider = _provider(lambda request: httpx.Response(302, headers={"location": "/other"}))

    assert provider._client._trust_env is False
    assert provider._client.follow_redirects is False

    with pytest.raises(ProviderHTTPError) as captured:
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())
    assert captured.value.status_code == 302


def test_error_logs_exclude_prompts_responses_and_bodies(caplog: pytest.LogCaptureFixture) -> None:
    secret = "SENSITIVE-PROMPT-AND-BODY"
    provider = _provider(lambda request: httpx.Response(500, json={"error": secret}))

    with (
        caplog.at_level(logging.WARNING, logger="kosmos"),
        pytest.raises(ProviderHTTPError),
    ):
        asyncio.run(provider.generate(_request()))

    asyncio.run(provider.aclose())
    assert secret not in caplog.text
    assert "Olá, Kosmos" not in caplog.text
