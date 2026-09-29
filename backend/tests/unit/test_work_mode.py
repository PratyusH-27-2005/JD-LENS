import pytest

from app.pipeline.normalize.result import Normalized
from app.pipeline.normalize.work_mode import parse_work_mode


@pytest.mark.parametrize(
    ("text", "mode", "days"),
    [
        ("Work from office, 5 days a week", "onsite", 5),
        ("On-site", "onsite", None),
        ("Remote", "remote", None),
        ("WFH", "remote", None),
        ("Hybrid (3 days in office)", "hybrid", 3),
    ],
)
def test_parse_work_mode_ok(text, mode, days):
    assert parse_work_mode(text) == Normalized(value={"mode": mode, "days_per_week": days})


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("Remote or onsite", "more than one work mode"),
        ("Flexible", "no work mode found"),
        # Kasparro's "virtual mode" is about the recruitment drive, not the job.
        ("virtual mode", "no work mode found"),
    ],
)
def test_parse_work_mode_ambiguous(text, reason_part):
    result = parse_work_mode(text)
    assert result.flag == "ambiguous"
    assert reason_part in result.reason
