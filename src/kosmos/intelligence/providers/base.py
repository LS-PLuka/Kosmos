"""Provider-independent contracts for language model inference."""

from typing import Protocol

from kosmos.intelligence.models import InferenceRequest, InferenceResponse


class LLMProvider(Protocol):
    """Asynchronous port for complete text generation."""

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate a complete textual response for a validated request."""
        ...
