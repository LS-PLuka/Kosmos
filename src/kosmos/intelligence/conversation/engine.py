"""In-memory conversation orchestration over the provider-independent inference port."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from kosmos.core.exceptions import (
    InvalidProviderResponseError,
    SessionBusyError,
    SessionNotFoundError,
)
from kosmos.intelligence.conversation.context import ContextPolicy
from kosmos.intelligence.conversation.models import ConversationSession
from kosmos.intelligence.models import (
    InferenceChunk,
    InferenceRequest,
    InferenceResponse,
    Message,
    MessageRole,
)
from kosmos.intelligence.providers.base import LLMProvider


@dataclass(slots=True)
class _ManagedSession:
    session_id: UUID
    system_instruction: str | None
    messages: list[Message] = field(default_factory=list)
    is_busy: bool = False

    def snapshot(self) -> ConversationSession:
        return ConversationSession(
            session_id=self.session_id,
            system_instruction=self.system_instruction,
            messages=tuple(self.messages),
            is_busy=self.is_busy,
        )


class ConversationStream(AsyncIterator[InferenceChunk]):
    """Stream one reserved turn and commit it only after valid provider completion."""

    def __init__(
        self,
        *,
        upstream: AsyncIterator[InferenceChunk],
        session: _ManagedSession,
        user_message: Message,
    ) -> None:
        self._upstream = upstream
        self._session = session
        self._user_message = user_message
        self._content_parts: list[str] = []
        self._closed = False

    def __aiter__(self) -> "ConversationStream":
        return self

    async def __anext__(self) -> InferenceChunk:
        if self._closed:
            raise StopAsyncIteration

        try:
            chunk = await anext(self._upstream)
        except StopAsyncIteration:
            await self.aclose()
            raise InvalidProviderResponseError(
                "provider stream ended before a completion event"
            ) from None
        except asyncio.CancelledError:
            await self._close_after_failure()
            raise
        except Exception:
            await self._close_after_failure()
            raise

        if not isinstance(chunk, InferenceChunk):
            await self.aclose()
            raise InvalidProviderResponseError("provider stream returned an invalid chunk")

        self._content_parts.append(chunk.content)

        if not chunk.done:
            return chunk

        content = "".join(self._content_parts)

        if not content.strip():
            await self.aclose()
            raise InvalidProviderResponseError("provider stream returned an empty response")

        try:
            await self._close_upstream()
        except asyncio.CancelledError:
            self._release()
            raise
        except Exception:
            self._release()
            raise

        self._session.messages.extend(
            (
                self._user_message,
                Message(MessageRole.ASSISTANT, content),
            )
        )
        self._release()

        return chunk

    async def aclose(self) -> None:
        """Close the provider iterator and discard any unconfirmed partial turn."""

        if self._closed:
            return

        try:
            await self._close_upstream()
        finally:
            self._release()

    async def _close_after_failure(self) -> None:
        try:
            await self._close_upstream()
        finally:
            self._release()

    async def _close_upstream(self) -> None:
        close = getattr(self._upstream, "aclose", None)

        if close is not None:
            await close()

    def _release(self) -> None:
        self._session.is_busy = False
        self._closed = True


class ConversationEngine:
    """Manage isolated in-memory sessions and provider-independent conversation turns."""

    def __init__(self, provider: LLMProvider, context_policy: ContextPolicy | None = None) -> None:
        if context_policy is not None and not isinstance(context_policy, ContextPolicy):
            raise TypeError("context_policy must be a ContextPolicy or None")

        self._provider = provider
        self._context_policy = context_policy or ContextPolicy()
        self._sessions: dict[UUID, _ManagedSession] = {}

    def create_session(self, *, system_instruction: str | None = None) -> ConversationSession:
        """Create and manage a new isolated session."""

        if system_instruction is not None:
            Message(MessageRole.SYSTEM, system_instruction)

        session_id = uuid4()
        session = _ManagedSession(
            session_id=session_id,
            system_instruction=system_instruction,
        )
        self._sessions[session_id] = session

        return session.snapshot()

    def get_session(self, session_id: UUID) -> ConversationSession:
        """Return a read-only snapshot of one session."""

        return self._get_managed_session(session_id).snapshot()

    def list_sessions(self) -> tuple[ConversationSession, ...]:
        """Return read-only snapshots in creation order."""

        return tuple(session.snapshot() for session in self._sessions.values())

    def clear_session(self, session_id: UUID) -> ConversationSession:
        """Clear confirmed turns while preserving session identity and system instruction."""

        session = self._get_managed_session(session_id)
        self._require_available(session)
        session.messages.clear()

        return session.snapshot()

    def delete_session(self, session_id: UUID) -> None:
        """Remove an idle session from in-memory management."""

        session = self._get_managed_session(session_id)
        self._require_available(session)
        del self._sessions[session_id]

    async def generate(
        self,
        session_id: UUID,
        content: str,
        *,
        model: str,
        thinking: bool | None = None,
    ) -> InferenceResponse:
        """Run and atomically commit one complete inference turn."""

        session, user_message, request = self._prepare_turn(
            session_id,
            content,
            model=model,
            thinking=thinking,
        )

        try:
            response = await self._provider.generate(request)

            if not isinstance(response, InferenceResponse):
                raise InvalidProviderResponseError("provider returned an invalid response")

            session.messages.extend(
                (
                    user_message,
                    Message(MessageRole.ASSISTANT, response.content),
                )
            )

            return response
        finally:
            session.is_busy = False

    async def run_turn(
        self,
        session_id: UUID,
        content: str,
        operation: Callable[[tuple[Message, ...]], Awaitable[str]],
    ) -> str:
        """Reserve one turn while a caller coordinates work and atomically commit its result."""

        if not callable(operation):
            raise TypeError("operation must be callable")

        session = self._get_managed_session(session_id)
        user_message = Message(MessageRole.USER, content)
        self._require_available(session)
        session.is_busy = True

        try:
            messages = self._context_policy.select(
                system_instruction=session.system_instruction,
                history=session.messages,
                current_message=user_message,
            )
            response_content = await operation(messages)
            assistant_message = Message(MessageRole.ASSISTANT, response_content)
            session.messages.extend((user_message, assistant_message))

            return response_content
        finally:
            session.is_busy = False

    def stream(
        self,
        session_id: UUID,
        content: str,
        *,
        model: str,
        thinking: bool | None = None,
    ) -> ConversationStream:
        """Reserve a session and return an incrementally consumed inference stream."""

        session, user_message, request = self._prepare_turn(
            session_id,
            content,
            model=model,
            thinking=thinking,
        )

        try:
            upstream = self._provider.stream(request)
        except Exception:
            session.is_busy = False
            raise

        if not isinstance(upstream, AsyncIterator):
            session.is_busy = False
            raise InvalidProviderResponseError("provider returned an invalid stream")

        return ConversationStream(
            upstream=upstream,
            session=session,
            user_message=user_message,
        )

    def _prepare_turn(
        self,
        session_id: UUID,
        content: str,
        *,
        model: str,
        thinking: bool | None,
    ) -> tuple[_ManagedSession, Message, InferenceRequest]:
        session = self._get_managed_session(session_id)
        user_message = Message(MessageRole.USER, content)
        self._validate_model_and_thinking(model, thinking)
        self._require_available(session)
        session.is_busy = True

        try:
            messages = self._context_policy.select(
                system_instruction=session.system_instruction,
                history=session.messages,
                current_message=user_message,
            )
            request = InferenceRequest(
                model=model,
                messages=messages,
                thinking=thinking,
            )
        except Exception:
            session.is_busy = False
            raise

        return session, user_message, request

    def _get_managed_session(self, session_id: UUID) -> _ManagedSession:
        if not isinstance(session_id, UUID):
            raise TypeError("session_id must be a UUID")

        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError("conversation session was not found") from None

    @staticmethod
    def _validate_model_and_thinking(model: str, thinking: bool | None) -> None:
        if not isinstance(model, str):
            raise TypeError("model must be a string")

        if not model.strip():
            raise ValueError("model must not be empty")

        if thinking is not None and not isinstance(thinking, bool):
            raise TypeError("thinking must be a boolean or None")

    @staticmethod
    def _require_available(session: _ManagedSession) -> None:
        if session.is_busy:
            raise SessionBusyError("conversation session is busy")
