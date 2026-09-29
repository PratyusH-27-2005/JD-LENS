"""The Kasparro notice, end to end through the pure core (no LLM).

The quotes below are what a well-behaved model should return as evidence.
"""

from pathlib import Path

import pytest

from app.pipeline.evidence import evidence_found
from app.pipeline.normalize.dates import parse_deadline
from app.pipeline.normalize.eligibility import parse_eligibility
from app.pipeline.normalize.money import parse_ctc, parse_stipend

NOTICE = (Path(__file__).parents[1] / "fixtures" / "postings" / "kasparro.txt").read_text(
    encoding="utf-8"
)

STIPEND = "Rs. 25,00 Per Month"
CTC = (
    "Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant of matching value. "
    "Total Rs. 10.00–Rs. 16.00 LPA"
)
DEADLINE = "30th Sept’2026 by 9.00 AM"
ELIGIBILITY = "6.00 or above CGPA in B.Tech, No Backlogs"


@pytest.mark.parametrize("quote", [STIPEND, CTC, DEADLINE, ELIGIBILITY, "Bengaluru"])
def test_quotes_are_in_the_notice(quote):
    assert evidence_found(quote, NOTICE)


def test_straightened_quote_still_verifies():
    # Models often turn ’ into '. That must not cost us the field.
    assert evidence_found("30th Sept'2026 by 9.00 AM", NOTICE)


def test_stipend_is_flagged_not_guessed():
    result = parse_stipend(STIPEND)
    assert result.flag == "ambiguous"
    assert result.value is None
    assert '"25,00" is not a valid digit grouping' in result.reason


def test_ctc_splits_cash_from_equity():
    assert parse_ctc(CTC).value == {
        "cash_min_inr": 500_000,
        "cash_max_inr": 800_000,
        "total_min_inr": 1_000_000,
        "total_max_inr": 1_600_000,
        "has_equity": True,
    }


def test_deadline():
    assert parse_deadline(DEADLINE).value == {
        "iso": "2026-09-30T09:00:00+05:30",
        "tz_assumed": True,
        "time_assumed": False,
    }


def test_eligibility():
    assert parse_eligibility(ELIGIBILITY).value == {"cgpa_min": 6.0, "backlogs_allowed": False}
