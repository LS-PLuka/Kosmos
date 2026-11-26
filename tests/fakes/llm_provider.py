"""Network-free LLM provider test double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from kosmos.intelligence.models import InferenceChunk, InferenceRequest, InferenceResponse


@dataclass(slots=True)
class FakeLLMProvider:
    """Return a configured response or raise a configured inference failure."""

    response: InferenceResponse | None = None
    chunks: tuple[InferenceChunk, ...] = ()
    error: Exception | None = None
    requests: list[InferenceRequest] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.response is None and not self.chunks and self.error is None:
            raise ValueError("a fake response, chunks, or error must be configured")

        configured_results = int(self.response is not None) + int(bool(self.chunks))

        if configured_results > 1 or (configured_results and self.error is not None):
            raise ValueError("configure one fake result or an error")

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        if self.response is None:  # Guarded by __post_init__; retained for type narrowing.
            raise AssertionError("fake provider has no configured response")

        return self.response

    async def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        for chunk in self.chunks:
            yield chunk
