from dataclasses import replace
from datetime import datetime

import pytest

from app.pipeline.normalize.dates import IST
from app.pipeline.scoring import (
    PostingFacts,
    Profile,
    check_eligibility,
    score_location,
    score_pay,
    score_posting,
    score_skills,
)

ME = Profile(
    skills=["Python", "FastAPI", "PostgreSQL", "React", "Next.js", "TypeScript"],
    cgpa=8.1,
    has_backlogs=False,
    preferred_locations=["Bangalore", "Pune"],
    min_cash_inr=600_000,
)
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=IST)
REQUIRED = ["postgres", "React.js", "nextjs", "Go"]


# --- skills -----------------------------------------------------------------


def test_skills_use_alias_map_case_insensitively():
    part = score_skills(ME, REQUIRED)
    assert part.included
    assert part.points == 37.5  # 3 of 4 × 50
    assert part.inputs["matched"] == ["postgresql", "react", "next.js"]
    assert part.inputs["missing"] == ["go"]


def test_skills_duplicates_after_aliasing_count_once():
    assert score_skills(ME, ["React", "react.js", "ReactJS"]).points == 50


@pytest.mark.parametrize("required", [None, []])
def test_skills_left_out_when_none_extracted(required):
    assert not score_skills(ME, required).included


# --- location ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "mode", "included", "points"),
    [
        ("Bengaluru", "onsite", True, 20),  # Bangalore alias
        ("Pune, Maharashtra", None, True, 20),
        ("Mumbai", "onsite", True, 0),
        (None, "remote", True, 20),
        ("Mumbai", "remote", True, 20),
        (None, "onsite", False, 0),
        (None, None, False, 0),
    ],
)
def test_location(location, mode, included, points):
    part = score_location(ME, location, mode)
    assert (part.included, part.points) == (included, points)


def test_location_left_out_without_preferences():
    assert not score_location(replace(ME, preferred_locations=[]), "Pune", "onsite").included


# --- pay --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cash_max", "included", "points"),
    [
        (800_000, True, 30),
        (600_000, True, 30),
        (300_000, True, 15),  # scaled linearly
        (None, False, 0),
    ],
)
def test_pay(cash_max, included, points):
    part = score_pay(ME, cash_max)
    assert (part.included, part.points) == (included, points)


def test_pay_left_out_without_profile_minimum():
    assert not score_pay(replace(ME, min_cash_inr=None), 800_000).included


# --- total score ------------------------------------------------------------


def test_score_all_parts_known():
    facts = PostingFacts(
        required_skills=REQUIRED, location="Bengaluru", work_mode="onsite", cash_max_inr=800_000
    )
    assert score_posting(ME, facts, NOW).score == 88  # 37.5 + 20 + 30 = 87.5


def test_score_no_skills_rescales_other_weights():
    facts = PostingFacts(location="Bengaluru", cash_max_inr=800_000)
    result = score_posting(ME, facts, NOW)
    assert result.score == 100  # 50 of 50 known points
    skills = next(p for p in result.parts if p.name == "skills")
    assert not skills.included


def test_score_partial_rescale():
    facts = PostingFacts(
        required_skills=["python", "fastapi", "rust", "java"], cash_max_inr=300_000
    )
    assert score_posting(ME, facts, NOW).score == 50  # 2 of 4 skills: (25 + 15) / 80


def test_score_none_when_nothing_known():
    assert score_posting(ME, PostingFacts(), NOW).score is None


# --- eligibility gate ---------------------------------------------------------

PAST = datetime(2026, 8, 1, tzinfo=IST)
FUTURE = datetime(2026, 9, 30, 9, 0, tzinfo=IST)


@pytest.mark.parametrize(
    ("cgpa", "has_backlogs", "cgpa_min", "allowed", "deadline", "status", "eligible"),
    [
        (5.9, False, 6.0, False, None, "not_eligible", False),
        (8.1, False, 6.0, False, None, "eligible", True),
        (6.0, False, 6.0, False, None, "eligible", True),  # boundary
        (8.1, True, 6.0, False, None, "not_eligible", False),
        (8.1, True, 6.0, True, None, "eligible", True),
        (8.1, False, None, False, None, "check_manually", None),
        (8.1, False, 6.0, None, None, "check_manually", None),
        (None, False, 6.0, False, None, "check_manually", None),
        (8.1, None, 6.0, False, None, "check_manually", None),
        (5.9, False, 6.0, None, None, "not_eligible", False),  # a known failure is decisive
        (8.1, False, 6.0, False, PAST, "closed", True),
        (8.1, False, 6.0, False, FUTURE, "eligible", True),
    ],
)
def test_eligibility(cgpa, has_backlogs, cgpa_min, allowed, deadline, status, eligible):
    profile = replace(ME, cgpa=cgpa, has_backlogs=has_backlogs)
    facts = PostingFacts(cgpa_min=cgpa_min, backlogs_allowed=allowed, deadline=deadline)
    result = check_eligibility(profile, facts, NOW)
    assert (result.status, result.eligible) == (status, eligible)


def test_eligibility_reasons_explain_failure():
    facts = PostingFacts(cgpa_min=6.0, backlogs_allowed=False)
    result = check_eligibility(replace(ME, cgpa=5.9), facts, NOW)
    assert any("5.9" in r and "6.0" in r for r in result.reasons)
