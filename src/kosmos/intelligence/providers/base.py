"""Provider-independent contracts for language model inference."""

from collections.abc import AsyncIterator
from typing import Protocol

from kosmos.intelligence.models import InferenceChunk, InferenceRequest, InferenceResponse


class LLMProvider(Protocol):
    """Asynchronous port for complete and streaming text generation."""

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate a complete textual response for a validated request."""
        ...

    def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        """Stream ordered chunks; callers must close an interrupted iterator."""
        ...
