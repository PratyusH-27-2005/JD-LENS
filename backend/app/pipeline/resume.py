"""Resume → profile suggestions. Same rule as postings: the model quotes, code judges.

Nothing here writes to the database. The result is a suggestion the user reviews in the
profile form and saves with PUT /profile.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.llm.prompt import RESUME_PROMPT_VERSION, render_resume_prompt
from app.llm.types import LLMClient
from app.pipeline.evidence import check_mention, value_in_evidence
from app.pipeline.llm_step import CallLog, extract_validated
from app.pipeline.normalize.cgpa import parse_cgpa
from app.pipeline.scoring import canonical_skill
from app.schemas.resume_v1 import ResumeV1

SCHEMA_VERSION = "1.0"

ResumeField = Literal["name", "cgpa", "skill"]


@dataclass(frozen=True)
class Suggestion:
    value: str
    evidence: str


@dataclass(frozen=True)
class CgpaSuggestion:
    value: float  # parsed by code from the evidence, never the model's number
    evidence: str


@dataclass(frozen=True)
class Rejected:
    field: ResumeField
    value: str | None
    reason: str


@dataclass(frozen=True)
class ResumeResult:
    calls: list[CallLog]
    model_name: str
    failure: str | None = None  # "llm_unavailable" / "extraction_invalid: ..."
    name: Suggestion | None = None
    cgpa: CgpaSuggestion | None = None
    skills: list[Suggestion] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = RESUME_PROMPT_VERSION


async def read_resume(text: str, client: LLMClient) -> ResumeResult:
    step = await extract_validated(
        client,
        ResumeV1,
        lambda error: render_resume_prompt(text, previous_error=error),
        RESUME_PROMPT_VERSION,
    )
    if step.parsed is None:
        return ResumeResult(step.calls, client.model_name, failure=step.failure)

    r = step.parsed
    rejected: list[Rejected] = []

    name = _verified("name", r.name.value, r.name.evidence, text, rejected)

    cgpa = None
    if quote := _verified("cgpa", r.cgpa.value, r.cgpa.evidence, text, rejected):
        parsed = parse_cgpa(quote.evidence)  # the number comes from the quote, by code
        if parsed.value is None:
            rejected.append(Rejected("cgpa", quote.value, parsed.reason or "couldn't parse"))
        else:
            cgpa = CgpaSuggestion(parsed.value["cgpa"], quote.evidence)

    skills: list[Suggestion] = []
    seen: set[str] = set()
    for s in r.skills:
        verified = _verified("skill", s.name, s.evidence, text, rejected)
        if verified and canonical_skill(verified.value) not in seen:
            seen.add(canonical_skill(verified.value))
            skills.append(verified)

    return ResumeResult(
        step.calls, client.model_name, name=name, cgpa=cgpa, skills=skills, rejected=rejected
    )


def _verified(
    field_name: ResumeField,
    value: str | None,
    evidence: str | None,
    text: str,
    rejected: list[Rejected],
) -> Suggestion | None:
    """The suggestion if its quote is in the resume and contains the value; else None
    (and a Rejected entry, unless the resume simply doesn't state it)."""
    flag = check_mention(value, evidence, text)
    if flag == "missing" or not value or not value.strip():
        return None
    if flag == "unverified" or evidence is None:
        rejected.append(Rejected(field_name, value, "quote not found in the resume"))
        return None
    if not value_in_evidence(value, evidence):
        rejected.append(Rejected(field_name, value, "value isn't in its own quote"))
        return None
    return Suggestion(value.strip(), evidence)
