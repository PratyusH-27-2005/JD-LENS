"""The resume contract, version 1.0. Do not edit: a change means resume_v2.py.

Deliberately separate from extraction_v1 (no shared classes), so each contract can
change without touching the other.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ResumeMention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None  # as written, e.g. "CGPA: 8.1/10"
    evidence: str | None  # exact substring of the resume


class ResumeSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str  # as written, e.g. "PostgreSQL"
    evidence: str  # exact substring of the resume that names it


class ResumeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    name: ResumeMention
    cgpa: ResumeMention  # current degree's CGPA, not school percentages
    skills: list[ResumeSkill]
