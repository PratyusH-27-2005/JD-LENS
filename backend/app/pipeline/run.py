"""Steps 2–6 of the pipeline: extract → validate (one retry) → verify → normalize → status.

The model's only job is step 2. Everything after it is plain Python, and every number
is parsed from the verified *evidence*, never from the model's "value".
Persisting (llm_calls, extracted_fields) and scoring against the profile happen in the
caller (Phase 3); this module returns everything they need.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError

from app.llm.prompt import PROMPT_VERSION, render_extract_prompt
from app.llm.types import LLMClient, LLMResponse, LLMUnavailable
from app.pipeline.evidence import check_mention, value_in_evidence
from app.pipeline.normalize.dates import parse_deadline
from app.pipeline.normalize.eligibility import parse_eligibility
from app.pipeline.normalize.money import parse_ctc, parse_stipend, reconcile
from app.pipeline.normalize.result import Flag, Normalized
from app.pipeline.normalize.work_mode import parse_work_mode
from app.pipeline.scoring import PostingFacts
from app.schemas.extraction_v1 import ExtractionV1, Mention

SCHEMA_VERSION = "1.0"
MAX_ATTEMPTS = 2  # one try + one retry with the validation error

Status = Literal["verified", "partial", "needs_review"]

_SINGLE_FIELDS = (
    "company",
    "role_title",
    "location",
    "work_mode",
    "eligibility",
    "application_deadline",
    "apply_instructions",
)
_MONEY_FIELDS = ("stipend", "ctc")
_CORE_FIELDS = ("company", "role_title")
_NORMALIZERS: dict[str, Callable[[str], Normalized]] = {
    "stipend": parse_stipend,
    "ctc": parse_ctc,
    "application_deadline": parse_deadline,
    "eligibility": parse_eligibility,
    "work_mode": parse_work_mode,
}
_REASONS = {
    "missing": "not stated in the posting",
    "unverified": "evidence not found in the posting text",
}


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
class FieldResult:
    """One row of extracted_fields."""

    field_name: str
    mention_index: int
    raw_value: str | None
    evidence: str | None
    evidence_verified: bool
    normalized: dict[str, Any] | None
    flag: Flag
    flag_reason: str | None

    @property
    def display_value(self) -> str | None:
        """What the API may show. Unverified evidence → None, always."""
        return self.raw_value if self.evidence_verified else None


@dataclass(frozen=True)
class PipelineResult:
    status: Status
    status_reason: str | None
    fields: list[FieldResult]
    calls: list[CallLog]
    facts: PostingFacts
    model_name: str
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = PROMPT_VERSION


async def run_extraction(clean_text: str, client: LLMClient) -> PipelineResult:
    calls: list[CallLog] = []
    error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = render_extract_prompt(clean_text, previous_error=error)
        try:
            response = await client.extract(prompt)
        except LLMUnavailable as e:
            calls.append(_log(client, attempt, None, parse_ok=False, error=f"llm_unavailable: {e}"))
            return _needs_review("llm_unavailable", calls, client)
        try:
            extraction = ExtractionV1.model_validate_json(response.text)
        except ValidationError as e:
            error = _short_error(e)
            calls.append(_log(client, attempt, response, parse_ok=False, error=error))
            continue
        calls.append(_log(client, attempt, response, parse_ok=True, error=None))
        fields = verify_and_normalize(extraction, clean_text)
        status, reason = decide_status(fields)
        return PipelineResult(
            status=status,
            status_reason=reason,
            fields=fields,
            calls=calls,
            facts=facts_for_scoring(fields),
            model_name=client.model_name,
        )
    return _needs_review(f"extraction_invalid: {error}", calls, client)


# --- steps 4 and 5: evidence, then normalization -------------------------------------


def verify_and_normalize(extraction: ExtractionV1, clean_text: str) -> list[FieldResult]:
    fields = [_check(name, 0, getattr(extraction, name), clean_text) for name in _SINGLE_FIELDS]
    for name in _MONEY_FIELDS:
        mentions = getattr(extraction, name) or [Mention(value=None, evidence=None)]
        fields += _reconcile([_check(name, i, m, clean_text) for i, m in enumerate(mentions)])
    skills = [Mention(value=s.name, evidence=s.evidence) for s in extraction.required_skills]
    for i, m in enumerate(skills or [Mention(value=None, evidence=None)]):
        fields.append(_check("required_skills", i, m, clean_text))
    return fields


def _check(name: str, index: int, m: Mention, clean_text: str) -> FieldResult:
    flag = check_mention(m.value, m.evidence, clean_text)
    if flag != "none":
        return FieldResult(name, index, m.value, m.evidence, False, None, flag, _REASONS[flag])
    if not value_in_evidence(m.value, m.evidence):
        return FieldResult(
            name, index, m.value, m.evidence, False, None, "unverified",
            "value does not appear in its own evidence",
        )  # fmt: skip
    normalizer = _NORMALIZERS.get(name)
    if normalizer is None or m.evidence is None:
        return FieldResult(name, index, m.value, m.evidence, True, None, "none", None)
    # Parse the verified quote, not the model's value: code is the judge.
    n = normalizer(m.evidence)
    return FieldResult(name, index, m.value, m.evidence, True, n.value, n.flag, n.reason)


def _reconcile(mentions: list[FieldResult]) -> list[FieldResult]:
    """Verified money mentions must agree; unverified ones don't get a vote."""
    idx = [i for i, f in enumerate(mentions) if f.evidence_verified]
    checked = reconcile(
        [Normalized(mentions[i].normalized, mentions[i].flag, mentions[i].flag_reason) for i in idx]
    )
    out = list(mentions)
    for i, r in zip(idx, checked, strict=True):
        out[i] = replace(mentions[i], normalized=r.value, flag=r.flag, flag_reason=r.reason)
    return out


# --- step 6: status and the facts scoring may use --------------------------------------


def decide_status(fields: list[FieldResult]) -> tuple[Status, str | None]:
    """Company and role verified and unflagged, or needs_review. "missing" isn't a problem
    (the posting just doesn't say); any other flag makes the posting partial."""
    unverified_core = [
        name
        for name in _CORE_FIELDS
        if not any(f.field_name == name and f.flag == "none" for f in fields)
    ]
    if unverified_core:
        return "needs_review", f"not verified: {', '.join(unverified_core)}"
    flagged = dict.fromkeys(
        f"{f.field_name} ({f.flag})" for f in fields if f.flag not in ("none", "missing")
    )
    if flagged:
        return "partial", f"flagged: {', '.join(flagged)}"
    return "verified", None


def facts_for_scoring(fields: list[FieldResult]) -> PostingFacts:
    """Only verified, unflagged fields reach the score; anything else stays unknown."""

    def ok(name: str) -> list[FieldResult]:
        return [f for f in fields if f.field_name == name and f.flag == "none"]

    def normalized(name: str, key: str) -> Any:
        found = ok(name)
        return found[0].normalized.get(key) if found and found[0].normalized else None

    skills = [f.raw_value for f in ok("required_skills") if f.raw_value]
    location = ok("location")
    deadline = normalized("application_deadline", "iso")
    return PostingFacts(
        required_skills=skills or None,
        location=location[0].raw_value if location else None,
        work_mode=normalized("work_mode", "mode"),
        cash_max_inr=normalized("ctc", "cash_max_inr"),
        cgpa_min=normalized("eligibility", "cgpa_min"),
        backlogs_allowed=normalized("eligibility", "backlogs_allowed"),
        deadline=datetime.fromisoformat(deadline) if deadline else None,
    )


# --- helpers ---------------------------------------------------------------------------


def _needs_review(reason: str, calls: list[CallLog], client: LLMClient) -> PipelineResult:
    return PipelineResult(
        status="needs_review",
        status_reason=reason,
        fields=[],
        calls=calls,
        facts=PostingFacts(),
        model_name=client.model_name,
    )


def _log(
    client: LLMClient,
    attempt: int,
    response: LLMResponse | None,
    *,
    parse_ok: bool,
    error: str | None,
) -> CallLog:
    return CallLog(
        attempt=attempt,
        prompt_version=PROMPT_VERSION,
        model=client.model_name,
        latency_ms=response.latency_ms if response else None,
        input_tokens=response.input_tokens if response else None,
        output_tokens=response.output_tokens if response else None,
        raw_response=response.text if response else None,
        parse_ok=parse_ok,
        error=error,
    )


def _short_error(e: ValidationError, limit: int = 3) -> str:
    """The first few validation errors, short enough to put back into the prompt."""
    errors = e.errors()
    parts = [
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
        for err in errors[:limit]
    ]
    more = f" (+{len(errors) - limit} more)" if len(errors) > limit else ""
    return ("; ".join(parts) + more)[:400]
