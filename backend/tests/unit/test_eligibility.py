import pytest

from app.pipeline.normalize.eligibility import parse_eligibility
from app.pipeline.normalize.result import Normalized


@pytest.mark.parametrize(
    ("text", "cgpa_min", "backlogs_allowed"),
    [
        ("6.00 or above CGPA in B.Tech, No Backlogs", 6.0, False),
        ("Minimum CGPA of 7.5, no active backlogs", 7.5, False),
        ("CGPA >= 8", 8.0, None),
        ("7+ CGPA throughout", 7.0, None),
        ("Max 1 active backlog allowed", None, True),
        ("Backlogs allowed", None, True),
        ("CGPA: 6.5 and above. Backlogs are not allowed.", 6.5, False),
        ("7 CGPA and zero backlogs", 7.0, False),
    ],
)
def test_parse_eligibility_ok(text, cgpa_min, backlogs_allowed):
    assert parse_eligibility(text) == Normalized(
        value={"cgpa_min": cgpa_min, "backlogs_allowed": backlogs_allowed}
    )


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("60% throughout academics", "no CGPA or backlog rule"),
        ("Open to all B.Tech students", "no CGPA or backlog rule"),
        ("CGPA 65 or above", "above 10"),
        ("7.0 CGPA for CSE, 7.5 CGPA for IT", "more than one CGPA cutoff"),
        ("No backlogs; backlogs allowed for lateral entry", "both allows and forbids"),
    ],
)
def test_parse_eligibility_ambiguous(text, reason_part):
    result = parse_eligibility(text)
    assert result.flag == "ambiguous"
    assert reason_part in result.reason
