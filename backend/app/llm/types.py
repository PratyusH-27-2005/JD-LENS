"""What the pipeline knows about an LLM. No SDK here: the pipeline and the tests' fake
client depend on this module, and only app/llm/client.py depends on the SDK."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class LLMUnavailable(Exception):
    """Timeout, network error, quota, or the provider is down. Not the model's fault."""


class LLMClient(Protocol):
    model_name: str

    async def extract(self, prompt: str) -> LLMResponse:
        """Send one prompt in JSON mode; return the raw text. Raise LLMUnavailable on failure."""
        ...
