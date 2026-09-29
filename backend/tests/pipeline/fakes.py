"""A scripted stand-in for the LLM, plus canned responses for the fixture postings."""

import json
from pathlib import Path
from typing import Any

from app.llm.types import LLMResponse
from app.pipeline.ingest import clean

FIXTURES = Path(__file__).parents[1] / "fixtures" / "postings"


def posting(name: str) -> str:
    return clean((FIXTURES / name).read_text(encoding="utf-8"))


class FakeLLMClient:
    """Returns the scripted responses in order (an Exception is raised instead of returned)
    and records every prompt it was sent."""

    model_name = "fake-model"

    def __init__(self, *responses: str | dict[str, Any] | Exception) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def extract(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        text = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return LLMResponse(text=text, input_tokens=100, output_tokens=50, latency_ms=5)


def m(value: str | None, evidence: str | None = None) -> dict[str, str | None]:
    """A mention whose evidence defaults to the value itself."""
    return {"value": value, "evidence": value if evidence is None else evidence}


NULL = m(None)


def acme_response(**overrides: Any) -> dict[str, Any]:
    response = {
        "schema_version": "1.0",
        "company": m("Acme Robotics"),
        "role_title": m("Backend Engineer Intern"),
        "location": m("Pune, Maharashtra"),
        "work_mode": m("Hybrid", "Hybrid, 3 days a week in office"),
        "stipend": [m("₹ 30,000 per month")],
        "ctc": [m("12 LPA")],
        "eligibility": m("Minimum CGPA of 7.0, no active backlogs"),
        "application_deadline": m("15 October 2026, 11:59 PM IST"),
        "apply_instructions": m("careers.acme.example/apply"),
        "required_skills": [
            {"name": s, "evidence": s} for s in ("Python", "FastAPI", "PostgreSQL", "Docker")
        ],
    }
    return response | overrides


KASPARRO_CTC = (
    "Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant of matching value. "
    "Total Rs. 10.00–Rs. 16.00 LPA"
)


def kasparro_response(**overrides: Any) -> dict[str, Any]:
    """What a well-behaved model returns for the Kasparro notice."""
    response = {
        "schema_version": "1.0",
        "company": m("Kasparro"),
        "role_title": m("Full Stack Engineer – Intern Pathway"),
        "location": m("Bengaluru"),
        "work_mode": NULL,
        "stipend": [m("Rs. 25,00 Per Month")],
        "ctc": [m(KASPARRO_CTC)],
        "eligibility": m("6.00 or above CGPA in B.Tech, No Backlogs"),
        "application_deadline": m("30th Sept’2026 by 9.00 AM"),
        "apply_instructions": m("Send an email to nehakannan@kasparro.com, hazel@kasparro.com"),
        "required_skills": [],
    }
    return response | overrides
