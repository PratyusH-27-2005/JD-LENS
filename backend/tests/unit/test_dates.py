import pytest

from app.pipeline.normalize.dates import parse_deadline
from app.pipeline.normalize.result import Normalized


@pytest.mark.parametrize(
    ("text", "iso", "tz_assumed", "time_assumed"),
    [
        ("30th Sept'2026 by 9.00 AM", "2026-09-30T09:00:00+05:30", True, False),
        ("30th Sept’2026 by 9.00 AM", "2026-09-30T09:00:00+05:30", True, False),
        ("September 30, 2026 11:59 PM IST", "2026-09-30T23:59:00+05:30", False, False),
        ("1 Oct 2026, 17:30", "2026-10-01T17:30:00+05:30", True, False),
        ("12 PM on 1st Oct 2026", "2026-10-01T12:00:00+05:30", True, False),
        ("5 Oct 2026 10 am UTC", "2026-10-05T10:00:00+00:00", False, False),
        ("noon, 3rd Nov 2026", "2026-11-03T12:00:00+05:30", True, False),
        ("2026-10-05", "2026-10-05T23:59:59+05:30", True, True),
        ("15/10/2026", "2026-10-15T23:59:59+05:30", True, True),
        ("05/05/2026", "2026-05-05T23:59:59+05:30", True, True),
        ("Oct 1 '26", "2026-10-01T23:59:59+05:30", True, True),
    ],
)
def test_parse_deadline_ok(text, iso, tz_assumed, time_assumed):
    assert parse_deadline(text) == Normalized(
        value={"iso": iso, "tz_assumed": tz_assumed, "time_assumed": time_assumed}
    )


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("30 Sept", "no year"),
        ("05/10/2026", "day/month or month/day"),
        ("31st Feb 2026", "not a real date"),
        ("ASAP", "no date found"),
        ("midnight, 30 Sept 2026", "midnight"),
        ("1 Oct 2026 or 5 Oct 2026", "more than one date"),
        ("1 Oct 2026 at 13 PM", "not a valid time"),
    ],
)
def test_parse_deadline_ambiguous(text, reason_part):
    result = parse_deadline(text)
    assert result.flag == "ambiguous"
    assert result.value is None
    assert reason_part in result.reason
