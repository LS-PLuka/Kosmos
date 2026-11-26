"""Behavioral tests for in-memory conversation orchestration."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError, dataclass, field
from uuid import UUID, uuid4

import pytest
from tests.fakes.llm_provider import FakeLLMProvider

from kosmos.core.exceptions import (
    ContextLimitExceededError,
    InvalidProviderResponseError,
    ProviderTimeoutError,
    SessionBusyError,
    SessionNotFoundError,
)
from kosmos.intelligence.conversation import ContextPolicy, ConversationEngine
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceMetrics,
    InferenceRequest,
    InferenceResponse,
    Message,
    MessageRole,
)

MODEL = "test-model"


@dataclass(slots=True)
class SequentialProvider:
    responses: list[InferenceResponse]
    requests: list[InferenceRequest] = field(default_factory=list)

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)
        return self.responses.pop(0)

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.requests.append(request)
        yield InferenceChunk(model=MODEL, content="streamed", done=True)


class BlockingProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.second_started = asyncio.Event()
        self.release = asyncio.Event()
        self.requests: list[InferenceRequest] = []

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)
        self.started.set()

        if len(self.requests) == 2:
            self.second_started.set()

        await self.release.wait()
        return InferenceResponse(model=MODEL, content="completed")

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.requests.append(request)
        self.started.set()
        await self.release.wait()
        yield InferenceChunk(model=MODEL, content="completed", done=True)


def _engine_with_response(content: str = "answer") -> tuple[ConversationEngine, FakeLLMProvider]:
    provider = FakeLLMProvider(response=InferenceResponse(model=MODEL, content=content))
    return ConversationEngine(provider), provider


def test_sessions_have_distinct_identifiers_and_creation_order() -> None:
    engine, _ = _engine_with_response()

    first = engine.create_session()
    second = engine.create_session(system_instruction="Be concise.")

    assert isinstance(first.session_id, UUID)
    assert first.session_id != second.session_id
    assert engine.get_session(second.session_id) == second
    assert engine.list_sessions() == (first, second)


def test_session_snapshot_is_immutable_and_does_not_expose_mutable_history() -> None:
    engine, _ = _engine_with_response()
    session = engine.create_session()

    assert isinstance(session.messages, tuple)

    with pytest.raises(FrozenInstanceError):
        session.is_busy = True  # type: ignore[misc]


def test_invalid_and_missing_session_identifiers_are_explicit() -> None:
    engine, _ = _engine_with_response()

    with pytest.raises(TypeError, match="UUID"):
        engine.get_session("not-a-uuid")  # type: ignore[arg-type]

    with pytest.raises(SessionNotFoundError, match="not found"):
        engine.get_session(uuid4())


def test_clear_preserves_identity_and_system_instruction() -> None:
    async def scenario() -> None:
        engine, _ = _engine_with_response()
        session = engine.create_session(system_instruction="Preserve this.")
        await engine.generate(session.session_id, "question", model=MODEL)

        cleared = engine.clear_session(session.session_id)

        assert cleared.session_id == session.session_id
        assert cleared.system_instruction == "Preserve this."
        assert cleared.messages == ()

    asyncio.run(scenario())


def test_delete_removes_session() -> None:
    engine, _ = _engine_with_response()
    session = engine.create_session()

    engine.delete_session(session.session_id)

    assert engine.list_sessions() == ()

    with pytest.raises(SessionNotFoundError):
        engine.get_session(session.session_id)


@pytest.mark.parametrize("instruction", ["", "   ", 42])
def test_session_rejects_invalid_system_instruction(instruction: object) -> None:
    engine, _ = _engine_with_response()

    with pytest.raises((TypeError, ValueError)):
        engine.create_session(system_instruction=instruction)  # type: ignore[arg-type]


def test_generate_records_complete_turn_and_preserves_provider_result() -> None:
    async def scenario() -> None:
        metrics = InferenceMetrics(eval_count=7)
        response = InferenceResponse(
            model="provider-model",
            content="  exact answer  ",
            metrics=metrics,
        )
        provider = FakeLLMProvider(response=response)
        engine = ConversationEngine(provider)
        session = engine.create_session()

        result = await engine.generate(
            session.session_id,
            "  exact question  ",
            model=MODEL,
            thinking=True,
        )

        assert result is response
        assert provider.requests[0].model == MODEL
        assert provider.requests[0].thinking is True
        assert provider.requests[0].messages == (Message(MessageRole.USER, "  exact question  "),)
        assert engine.get_session(session.session_id).messages == (
            Message(MessageRole.USER, "  exact question  "),
            Message(MessageRole.ASSISTANT, "  exact answer  "),
        )

    asyncio.run(scenario())


def test_multiple_inferences_send_confirmed_history_as_context() -> None:
    async def scenario() -> None:
        provider = SequentialProvider(
            responses=[
                InferenceResponse(model=MODEL, content="first answer"),
                InferenceResponse(model=MODEL, content="second answer"),
            ]
        )
        engine = ConversationEngine(provider)
        session = engine.create_session(system_instruction="System instruction")

        await engine.generate(session.session_id, "first question", model=MODEL)
        await engine.generate(session.session_id, "second question", model=MODEL)

        assert provider.requests[1].messages == (
            Message(MessageRole.SYSTEM, "System instruction"),
            Message(MessageRole.USER, "first question"),
            Message(MessageRole.ASSISTANT, "first answer"),
            Message(MessageRole.USER, "second question"),
        )

    asyncio.run(scenario())


def test_sessions_keep_history_isolated() -> None:
    async def scenario() -> None:
        provider = SequentialProvider(
            responses=[
                InferenceResponse(model=MODEL, content="answer one"),
                InferenceResponse(model=MODEL, content="answer two"),
            ]
        )
        engine = ConversationEngine(provider)
        first = engine.create_session()
        second = engine.create_session()

        await engine.generate(first.session_id, "question one", model=MODEL)
        await engine.generate(second.session_id, "question two", model=MODEL)

        assert [message.content for message in provider.requests[1].messages] == ["question two"]
        assert engine.get_session(first.session_id).messages[0].content == "question one"
        assert engine.get_session(second.session_id).messages[0].content == "question two"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("content", "model", "thinking"),
    [
        ("", MODEL, None),
        ("   ", MODEL, None),
        (42, MODEL, None),
        ("question", "", None),
        ("question", 42, None),
        ("question", MODEL, "yes"),
    ],
)
def test_generate_rejects_invalid_turn_input(
    content: object,
    model: object,
    thinking: object,
) -> None:
    async def scenario() -> None:
        engine, provider = _engine_with_response()
        session = engine.create_session()

        with pytest.raises((TypeError, ValueError)):
            await engine.generate(
                session.session_id,
                content,  # type: ignore[arg-type]
                model=model,  # type: ignore[arg-type]
                thinking=thinking,  # type: ignore[arg-type]
            )

        assert provider.requests == []
        assert engine.get_session(session.session_id).messages == ()

    asyncio.run(scenario())


@pytest.mark.parametrize("error", [RuntimeError("failed"), ProviderTimeoutError("timed out")])
def test_provider_failure_does_not_change_history_and_releases_session(error: Exception) -> None:
    async def scenario() -> None:
        provider = FakeLLMProvider(error=error)
        engine = ConversationEngine(provider)
        session = engine.create_session()

        with pytest.raises(type(error)):
            await engine.generate(session.session_id, "question", model=MODEL)

        snapshot = engine.get_session(session.session_id)
        assert snapshot.messages == ()
        assert snapshot.is_busy is False

    asyncio.run(scenario())


def test_context_failure_happens_before_provider_call_and_releases_session() -> None:
    async def scenario() -> None:
        engine, provider = _engine_with_response()
        engine = ConversationEngine(provider, ContextPolicy(max_context_characters=5))
        session = engine.create_session(system_instruction="123")

        with pytest.raises(ContextLimitExceededError):
            await engine.generate(session.session_id, "456", model=MODEL)

        assert provider.requests == []
        assert engine.get_session(session.session_id).is_busy is False

    asyncio.run(scenario())


def test_invalid_provider_response_is_not_committed() -> None:
    class InvalidProvider:
        async def generate(self, request: InferenceRequest) -> object:
            return object()

        async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
            yield InferenceChunk(model=MODEL, content="unused", done=True)

    async def scenario() -> None:
        engine = ConversationEngine(InvalidProvider())  # type: ignore[arg-type]
        session = engine.create_session()

        with pytest.raises(InvalidProviderResponseError, match="invalid response"):
            await engine.generate(session.session_id, "question", model=MODEL)

        assert engine.get_session(session.session_id).messages == ()

    asyncio.run(scenario())


def test_generate_cancellation_preserves_history_and_releases_session() -> None:
    async def scenario() -> None:
        provider = BlockingProvider()
        engine = ConversationEngine(provider)
        session = engine.create_session()
        task = asyncio.create_task(engine.generate(session.session_id, "question", model=MODEL))
        await provider.started.wait()

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        snapshot = engine.get_session(session.session_id)
        assert snapshot.messages == ()
        assert snapshot.is_busy is False

    asyncio.run(scenario())


def test_busy_session_rejects_other_turn_clear_and_delete() -> None:
    async def scenario() -> None:
        provider = BlockingProvider()
        engine = ConversationEngine(provider)
        session = engine.create_session()
        task = asyncio.create_task(engine.generate(session.session_id, "first", model=MODEL))
        await provider.started.wait()

        with pytest.raises(SessionBusyError):
            await engine.generate(session.session_id, "second", model=MODEL)

        with pytest.raises(SessionBusyError):
            engine.clear_session(session.session_id)

        with pytest.raises(SessionBusyError):
            engine.delete_session(session.session_id)

        provider.release.set()
        await task

    asyncio.run(scenario())


def test_different_sessions_can_generate_independently() -> None:
    async def scenario() -> None:
        provider = BlockingProvider()
        engine = ConversationEngine(provider)
        first = engine.create_session()
        second = engine.create_session()
        first_task = asyncio.create_task(engine.generate(first.session_id, "first", model=MODEL))
        await provider.started.wait()
        second_task = asyncio.create_task(engine.generate(second.session_id, "second", model=MODEL))
        await provider.second_started.wait()

        assert len(provider.requests) == 2

        provider.release.set()
        await asyncio.gather(first_task, second_task)

    asyncio.run(scenario())


def test_stream_delivers_chunks_incrementally_and_commits_exact_content() -> None:
    async def scenario() -> None:
        metrics = InferenceMetrics(eval_count=3)
        chunks = (
            InferenceChunk(model=MODEL, content="Olá", done=False),
            InferenceChunk(model=MODEL, content=" ", done=False),
            InferenceChunk(model=MODEL, content="mundo", done=False),
            InferenceChunk(model=MODEL, content="!", done=True, metrics=metrics),
        )
        provider = FakeLLMProvider(chunks=chunks)
        engine = ConversationEngine(provider)
        session = engine.create_session()
        stream = engine.stream(session.session_id, "question", model=MODEL, thinking=False)

        first = await anext(stream)
        assert first is chunks[0]
        assert engine.get_session(session.session_id).messages == ()

        received = [first]
        async for chunk in stream:
            received.append(chunk)

        assert received == list(chunks)
        assert provider.requests[0].thinking is False
        assert engine.get_session(session.session_id).messages == (
            Message(MessageRole.USER, "question"),
            Message(MessageRole.ASSISTANT, "Olá mundo!"),
        )

    asyncio.run(scenario())


def test_stream_accepts_empty_intermediate_and_content_in_final_event() -> None:
    async def scenario() -> None:
        chunks = (
            InferenceChunk(model=MODEL, content="", done=False),
            InferenceChunk(model=MODEL, content="final content", done=True),
        )
        provider = FakeLLMProvider(chunks=chunks)
        engine = ConversationEngine(provider)
        session = engine.create_session()

        received = [
            chunk async for chunk in engine.stream(session.session_id, "question", model=MODEL)
        ]

        assert received == list(chunks)
        assert engine.get_session(session.session_id).messages[-1].content == "final content"

    asyncio.run(scenario())


def test_stream_accepts_empty_final_event_after_text_content() -> None:
    async def scenario() -> None:
        chunks = (
            InferenceChunk(model=MODEL, content="complete response", done=False),
            InferenceChunk(model=MODEL, content="", done=True),
        )
        provider = FakeLLMProvider(chunks=chunks)
        engine = ConversationEngine(provider)
        session = engine.create_session()

        received = [
            chunk async for chunk in engine.stream(session.session_id, "question", model=MODEL)
        ]

        assert received == list(chunks)
        assert len(provider.requests) == 1
        assert engine.get_session(session.session_id).messages[-1].content == "complete response"

    asyncio.run(scenario())


def test_stream_rejects_whitespace_only_final_response() -> None:
    async def scenario() -> None:
        provider = FakeLLMProvider(
            chunks=(
                InferenceChunk(model=MODEL, content=" ", done=False),
                InferenceChunk(model=MODEL, content="\t", done=True),
            )
        )
        engine = ConversationEngine(provider)
        session = engine.create_session()

        with pytest.raises(InvalidProviderResponseError, match="empty response"):
            async for _ in engine.stream(session.session_id, "question", model=MODEL):
                pass

        assert engine.get_session(session.session_id).messages == ()
        assert engine.get_session(session.session_id).is_busy is False

    asyncio.run(scenario())


def test_premature_stream_end_does_not_commit_partial_content() -> None:
    async def scenario() -> None:
        provider = FakeLLMProvider(
            chunks=(InferenceChunk(model=MODEL, content="partial", done=False),)
        )
        engine = ConversationEngine(provider)
        session = engine.create_session()

        with pytest.raises(InvalidProviderResponseError, match="before a completion"):
            async for _ in engine.stream(session.session_id, "question", model=MODEL):
                pass

        assert engine.get_session(session.session_id).messages == ()

    asyncio.run(scenario())


def test_stream_failure_after_partial_content_does_not_commit() -> None:
    class FailingStreamProvider:
        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            raise AssertionError("not used")

        async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
            yield InferenceChunk(model=MODEL, content="partial", done=False)
            raise ProviderTimeoutError("timed out")

    async def scenario() -> None:
        engine = ConversationEngine(FailingStreamProvider())
        session = engine.create_session()

        with pytest.raises(ProviderTimeoutError):
            async for _ in engine.stream(session.session_id, "question", model=MODEL):
                pass

        snapshot = engine.get_session(session.session_id)
        assert snapshot.messages == ()
        assert snapshot.is_busy is False

    asyncio.run(scenario())


def test_early_stream_close_closes_upstream_and_releases_session() -> None:
    class ClosingProvider:
        def __init__(self) -> None:
            self.closed = False

        async def generate(self, request: InferenceRequest) -> InferenceResponse:
            raise AssertionError("not used")

        async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
            try:
                yield InferenceChunk(model=MODEL, content="partial", done=False)
                yield InferenceChunk(model=MODEL, content="complete", done=True)
            finally:
                self.closed = True

    async def scenario() -> None:
        provider = ClosingProvider()
        engine = ConversationEngine(provider)
        session = engine.create_session()
        stream = engine.stream(session.session_id, "question", model=MODEL)

        assert (await anext(stream)).content == "partial"
        await stream.aclose()

        assert provider.closed is True
        snapshot = engine.get_session(session.session_id)
        assert snapshot.messages == ()
        assert snapshot.is_busy is False

    asyncio.run(scenario())


def test_unconsumed_stream_reserves_session_until_explicitly_closed() -> None:
    async def scenario() -> None:
        provider = FakeLLMProvider(
            chunks=(InferenceChunk(model=MODEL, content="complete", done=True),)
        )
        engine = ConversationEngine(provider)
        session = engine.create_session()

        stream = engine.stream(session.session_id, "question", model=MODEL)

        with pytest.raises(SessionBusyError):
            engine.clear_session(session.session_id)

        await stream.aclose()
        assert engine.get_session(session.session_id).is_busy is False

    asyncio.run(scenario())


def test_stream_cancellation_closes_upstream_and_releases_session() -> None:
    async def scenario() -> None:
        provider = BlockingProvider()
        engine = ConversationEngine(provider)
        session = engine.create_session()
        stream = engine.stream(session.session_id, "question", model=MODEL)
        task = asyncio.create_task(anext(stream))
        await provider.started.wait()

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        snapshot = engine.get_session(session.session_id)
        assert snapshot.messages == ()
        assert snapshot.is_busy is False

    asyncio.run(scenario())


def test_conversation_content_is_not_written_to_logs(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        engine, _ = _engine_with_response("private answer")
        session = engine.create_session()
        await engine.generate(session.session_id, "private question", model=MODEL)

    asyncio.run(scenario())

    log_text = caplog.text
    assert "private question" not in log_text
    assert "private answer" not in log_text
