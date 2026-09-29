"""The one place an LLM answer enters the pipeline: call, validate against a contract,
retry once with the validation error, and fail closed. Used for postings and resumes."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.llm.types import LLMClient, LLMResponse, LLMUnavailable

MAX_ATTEMPTS = 2  # one try + one retry with the validation error


@dataclass(frozen=True)
class CallLog:
    """One row of llm_calls."""

    attempt: int
    prompt_version: str
    model: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    raw_response: str | None
    parse_ok: bool
    error: str | None


@dataclass(frozen=True)
class StepResult[T: BaseModel]:
    parsed: T | None
    calls: list[CallLog]
    # None on success; "llm_unavailable" or "extraction_invalid: <short error>" otherwise.
    failure: str | None


async def extract_validated[T: BaseModel](
    client: LLMClient,
    schema: type[T],
    render: Callable[[str | None], str],
    prompt_version: str,
) -> StepResult[T]:
    """`render(previous_error)` builds the prompt; the error is None on the first attempt."""
    calls: list[CallLog] = []
    error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.extract(render(error))
        except LLMUnavailable as e:
            calls.append(
                _log(client, prompt_version, attempt, None, False, f"llm_unavailable: {e}")
            )
            return StepResult(None, calls, "llm_unavailable")
        try:
            parsed = schema.model_validate_json(response.text)
        except ValidationError as e:
            error = short_error(e)
            calls.append(_log(client, prompt_version, attempt, response, False, error))
            continue
        calls.append(_log(client, prompt_version, attempt, response, True, None))
        return StepResult(parsed, calls, None)
    return StepResult(None, calls, f"extraction_invalid: {error}")


def short_error(e: ValidationError, limit: int = 3) -> str:
    """The first few validation errors, short enough to put back into the prompt."""
    errors = e.errors()
    parts = [
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
        for err in errors[:limit]
    ]
    more = f" (+{len(errors) - limit} more)" if len(errors) > limit else ""
    return ("; ".join(parts) + more)[:400]


def _log(
    client: LLMClient,
    prompt_version: str,
    attempt: int,
    response: LLMResponse | None,
    parse_ok: bool,
    error: str | None,
) -> CallLog:
    return CallLog(
        attempt=attempt,
        prompt_version=prompt_version,
        model=client.model_name,
        latency_ms=response.latency_ms if response else None,
        input_tokens=response.input_tokens if response else None,
        output_tokens=response.output_tokens if response else None,
        raw_response=response.text if response else None,
        parse_ok=parse_ok,
        error=error,
    )
