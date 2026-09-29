"""The ONLY module that imports the LLM SDK (enforced by tests/test_guard.py).

Swapping providers means rewriting this file and nothing else.
"""

import asyncio
import time
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import Settings, get_settings
from app.llm.types import LLMClient, LLMResponse, LLMUnavailable


class GeminiClient:
    def __init__(self, api_key: str, model_name: str, timeout_s: float) -> None:
        self.model_name = model_name
        self._timeout_s = timeout_s
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )
        self._config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiClient":
        return cls(settings.llm_api_key, settings.llm_model, settings.llm_timeout_s)

    async def extract(self, prompt: str) -> LLMResponse:
        start = time.perf_counter()
        try:
            # The SDK has its own timeout; wait_for is the backstop so we never hang.
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model_name, contents=prompt, config=self._config
                ),
                timeout=self._timeout_s + 1,
            )
        except TimeoutError as e:
            raise LLMUnavailable(f"timeout after {self._timeout_s:g}s") from e
        except Exception as e:  # network, auth, quota, 5xx: all "provider unavailable"
            raise LLMUnavailable(f"{type(e).__name__}: {str(e)[:200]}") from e

        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            latency_ms=round((time.perf_counter() - start) * 1000),
        )


@lru_cache
def get_llm_client() -> LLMClient:
    """FastAPI dependency. Tests override it with a FakeLLMClient."""
    return GeminiClient.from_settings(get_settings())
