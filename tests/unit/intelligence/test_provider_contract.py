"""Behavioral tests for the asynchronous LLM provider port."""

import asyncio

import pytest
from tests.fakes.llm_provider import FakeLLMProvider

from kosmos.core.exceptions import InferenceError
from kosmos.intelligence.models import (
    InferenceRequest,
    InferenceResponse,
    Message,
    MessageRole,
)
from kosmos.intelligence.providers import LLMProvider


def _request() -> InferenceRequest:
    return InferenceRequest("test-model", (Message(MessageRole.USER, "Hello"),))


async def _generate(provider: LLMProvider, request: InferenceRequest) -> InferenceResponse:
    return await provider.generate(request)


def test_uses_contract_with_a_deterministic_fake() -> None:
    request = _request()
    response = InferenceResponse("test-model", "Configured answer")
    provider = FakeLLMProvider(response=response)

    result = asyncio.run(_generate(provider, request))

    assert result is response
    assert provider.requests == [request]


def test_propagates_a_simulated_inference_failure() -> None:
    request = _request()
    provider = FakeLLMProvider(error=InferenceError("simulated failure"))

    with pytest.raises(InferenceError, match="simulated failure"):
        asyncio.run(_generate(provider, request))

    assert provider.requests == [request]
