"""Provider contracts for the intelligence domain."""

from kosmos.intelligence.providers.base import LLMProvider, ToolCallingProvider
from kosmos.intelligence.providers.ollama import OllamaModel, OllamaProvider

__all__ = ["LLMProvider", "OllamaModel", "OllamaProvider", "ToolCallingProvider"]
