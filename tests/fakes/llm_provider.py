"""Network-free LLM provider test double."""

from dataclasses import dataclass, field

from kosmos.intelligence.models import InferenceRequest, InferenceResponse


@dataclass(slots=True)
class FakeLLMProvider:
    """Return a configured response or raise a configured inference failure."""

    response: InferenceResponse | None = None
    error: Exception | None = None
    requests: list[InferenceRequest] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.response is None and self.error is None:
            raise ValueError("a fake response or error must be configured")

        if self.response is not None and self.error is not None:
            raise ValueError("configure either a fake response or an error, not both")

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        if self.response is None:  # Guarded by __post_init__; retained for type narrowing.
            raise AssertionError("fake provider has no configured response")

        return self.response
