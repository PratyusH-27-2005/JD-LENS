"""The LLM contract, version 1.0. Do not edit: a change means extraction_v2.py."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Mention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None  # as written, e.g. "Rs. 25,00 Per Month"
    evidence: str | None  # exact substring of the posting


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    evidence: str


class ExtractionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    company: Mention
    role_title: Mention
    location: Mention
    work_mode: Mention  # onsite / remote / hybrid, as written
    stipend: list[Mention]
    ctc: list[Mention]
    eligibility: Mention
    application_deadline: Mention
    apply_instructions: Mention
    required_skills: list[Skill]
