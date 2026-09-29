"""Fit score and eligibility gate. Plain, deterministic Python.

Callers must build PostingFacts from verified, unflagged fields only; anything else is
None and treated as unknown. A score part with unknown inputs is left out and the
remaining weights are rescaled to 100. Eligibility is a separate badge, never folded
into the score.
"""

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

WEIGHTS = {"skills": 50, "location": 20, "pay": 30}

SKILL_ALIASES = {
    "postgres": "postgresql",
    "react.js": "react",
    "reactjs": "react",
    "nextjs": "next.js",
    "node": "node.js",
    "nodejs": "node.js",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "k8s": "kubernetes",
    "tailwindcss": "tailwind",
    "tailwind css": "tailwind",
}
CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "gurgaon": "gurugram",
    "calcutta": "kolkata",
    "madras": "chennai",
    "new delhi": "delhi",
}


@dataclass(frozen=True)
class Profile:
    skills: list[str]
    cgpa: float | None
    has_backlogs: bool | None
    preferred_locations: list[str]
    min_cash_inr: int | None


@dataclass(frozen=True)
class PostingFacts:
    """Only values from verified, unflagged fields. Anything else must be None (unknown)."""

    required_skills: list[str] | None = None
    location: str | None = None
    work_mode: str | None = None
    cash_max_inr: int | None = None
    cgpa_min: float | None = None
    backlogs_allowed: bool | None = None
    deadline: datetime | None = None


@dataclass(frozen=True)
class Part:
    name: str
    weight: int
    included: bool
    points: float
    inputs: dict[str, Any]
    note: str


@dataclass(frozen=True)
class Eligibility:
    status: Literal["eligible", "not_eligible", "check_manually", "closed"]
    eligible: bool | None
    reasons: list[str]


@dataclass(frozen=True)
class ScoreResult:
    score: int | None
    eligibility: Eligibility
    parts: list[Part]

    def breakdown(self) -> dict[str, Any]:
        """JSON for match_scores.breakdown: enough for the UI to explain every point."""
        return {
            "score": self.score,
            "parts": {p.name: asdict(p) for p in self.parts},
            "eligibility": asdict(self.eligibility),
        }


# --- score parts ----------------------------------------------------------------


def canonical_skill(name: str) -> str:
    key = " ".join(name.lower().split())
    return SKILL_ALIASES.get(key, key)


def score_skills(profile: Profile, required: list[str] | None) -> Part:
    weight = WEIGHTS["skills"]
    if not required:
        return _left_out("skills", weight, "no required skills extracted")
    needed = list(dict.fromkeys(canonical_skill(s) for s in required))
    have = {canonical_skill(s) for s in profile.skills}
    matched = [s for s in needed if s in have]
    missing = [s for s in needed if s not in have]
    return Part(
        name="skills",
        weight=weight,
        included=True,
        points=weight * len(matched) / len(needed),
        inputs={"matched": matched, "missing": missing},
        note=f"{len(matched)} of {len(needed)} required skills",
    )


def score_location(profile: Profile, location: str | None, work_mode: str | None) -> Part:
    weight = WEIGHTS["location"]
    inputs = {"location": location, "work_mode": work_mode}
    if work_mode == "remote":
        return Part("location", weight, True, weight, inputs, "remote role")
    if not profile.preferred_locations:
        return _left_out("location", weight, "no preferred locations in profile")
    if location is None:
        return _left_out("location", weight, "location unknown")
    place = _canonical_place(location)
    hit = next(
        (p for p in profile.preferred_locations if _mentions(place, _canonical_place(p))), None
    )
    note = f"matches preferred location {hit}" if hit else "not a preferred location"
    return Part("location", weight, True, weight if hit else 0, inputs, note)


def score_pay(profile: Profile, cash_max_inr: int | None) -> Part:
    """Cash only: equity is never counted. Linear below the profile's minimum."""
    weight = WEIGHTS["pay"]
    minimum = profile.min_cash_inr
    if minimum is None:
        return _left_out("pay", weight, "no minimum cash in profile")
    if cash_max_inr is None:
        return _left_out("pay", weight, "cash pay unknown")
    inputs = {"cash_max_inr": cash_max_inr, "min_cash_inr": minimum}
    if minimum <= 0 or cash_max_inr >= minimum:
        return Part("pay", weight, True, weight, inputs, "meets your minimum")
    points = weight * cash_max_inr / minimum
    return Part("pay", weight, True, points, inputs, "below your minimum")


# --- eligibility gate -------------------------------------------------------------


def check_eligibility(profile: Profile, facts: PostingFacts, now: datetime) -> Eligibility:
    """A known failure is decisive; otherwise any unknown means "check manually"."""
    failures: list[str] = []
    unknowns: list[str] = []

    if facts.cgpa_min is None:
        unknowns.append("CGPA cutoff unknown")
    elif profile.cgpa is None:
        unknowns.append("your CGPA is not set")
    elif profile.cgpa < facts.cgpa_min:
        failures.append(f"CGPA {profile.cgpa} is below the {facts.cgpa_min} cutoff")

    if facts.backlogs_allowed is None:
        unknowns.append("backlog rule unknown")
    elif not facts.backlogs_allowed:
        if profile.has_backlogs is None:
            unknowns.append("your backlog status is not set")
        elif profile.has_backlogs:
            failures.append("backlogs are not allowed")

    eligible = False if failures else (None if unknowns else True)
    reasons = failures + unknowns
    if facts.deadline is not None and facts.deadline <= now:
        return Eligibility("closed", eligible, ["deadline has passed", *reasons])
    if failures:
        return Eligibility("not_eligible", eligible, reasons)
    if unknowns:
        return Eligibility("check_manually", eligible, reasons)
    return Eligibility("eligible", eligible, reasons)


# --- total ------------------------------------------------------------------------


def score_posting(profile: Profile, facts: PostingFacts, now: datetime) -> ScoreResult:
    parts = [
        score_skills(profile, facts.required_skills),
        score_location(profile, facts.location, facts.work_mode),
        score_pay(profile, facts.cash_max_inr),
    ]
    return ScoreResult(
        score=_combine(parts),
        eligibility=check_eligibility(profile, facts, now),
        parts=parts,
    )


def _combine(parts: list[Part]) -> int | None:
    """Sum of included points, rescaled so the included weights add up to 100."""
    included = [p for p in parts if p.included]
    if not included:
        return None
    raw = sum(p.points for p in included) / sum(p.weight for p in included) * 100
    return int(Decimal(str(raw)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _left_out(name: str, weight: int, note: str) -> Part:
    return Part(name=name, weight=weight, included=False, points=0, inputs={}, note=note)


def _canonical_place(s: str) -> str:
    s = " ".join(s.lower().split())
    for alias, canon in CITY_ALIASES.items():
        s = re.sub(rf"\b{re.escape(alias)}\b", canon, s)
    return s


def _mentions(place: str, preferred: str) -> bool:
    return re.search(rf"\b{re.escape(preferred)}\b", place) is not None
