"""Request and response models. The API never exposes a value whose evidence failed."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["pending", "verified", "partial", "needs_review"]
FlagName = Literal["none", "ambiguous", "conflict", "unverified", "missing"]
Badge = Literal["eligible", "not_eligible", "check_manually", "closed"]

MIN_POSTING_CHARS = 200
MAX_POSTING_CHARS = 50_000


class PostingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_text: str = Field(min_length=MIN_POSTING_CHARS, max_length=MAX_POSTING_CHARS)
    source_label: str | None = Field(default=None, max_length=200)


class FieldOut(BaseModel):
    field_name: str
    mention_index: int
    value: str | None = Field(description="null unless the evidence was found in the text")
    evidence: str | None = Field(description="null unless it was found in the text")
    evidence_verified: bool
    normalized: dict[str, Any] | None
    flag: FlagName
    flag_reason: str | None


class ScoreOut(BaseModel):
    score: int | None
    eligible: bool | None
    badge: Badge
    breakdown: dict[str, Any]
    computed_at: datetime


class PostingSummary(BaseModel):
    id: uuid.UUID
    status: Status
    source_label: str | None
    company: str | None
    role_title: str | None
    deadline: datetime | None
    cash_min_inr: int | None
    cash_max_inr: int | None
    score: int | None
    scored_on: list[str] = Field(
        description="score parts that had enough verified input, e.g. ['location', 'pay']"
    )
    eligible: bool | None
    badge: Badge
    created_at: datetime


class PostingDetail(BaseModel):
    id: uuid.UUID
    status: Status
    status_reason: str | None
    source_label: str | None
    raw_text: str
    clean_text: str
    schema_version: str | None
    prompt_version: str | None
    model_name: str | None
    created_at: datetime
    processed_at: datetime | None
    fields: list[FieldOut]
    score: ScoreOut | None


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=200)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    has_backlogs: bool | None = None
    preferred_locations: list[str] = Field(default_factory=list, max_length=50)
    min_cash_inr: int | None = Field(default=None, ge=0)


class ProfileOut(ProfileIn):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    updated_at: datetime | None = None


class ResumeValue(BaseModel):
    value: str
    evidence: str = Field(description="exact quote from the resume, verified by code")


class ResumeCgpa(BaseModel):
    value: float = Field(description="parsed by code from the quote")
    evidence: str


class ResumeSkillOut(ResumeValue):
    new: bool = Field(description="not already in the profile (aliases considered)")


class ResumeRejected(BaseModel):
    field: Literal["name", "cgpa", "skill"]
    value: str | None
    reason: str


class ResumeImport(BaseModel):
    """Suggestions only: the profile is not changed until PUT /profile."""

    name: ResumeValue | None
    cgpa: ResumeCgpa | None
    skills: list[ResumeSkillOut]
    rejected: list[ResumeRejected]
    model_name: str
    prompt_version: str
    text_chars: int


class HealthResponse(BaseModel):
    db: Literal["ok", "error"]
    llm_configured: bool


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
