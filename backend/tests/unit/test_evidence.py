import pytest

from app.pipeline.evidence import check_mention, evidence_found, normalize_for_match

TEXT = (
    "Stipend : Rs. 25,00 Per Month\n"
    "CTC : Rs. 5.00 –Rs. 8.00 LPA cash\n"
    "REGISTER on or before 30th Sept’2026 by 9.00 AM\n"
    "Joining Location :   Bengaluru"
)


@pytest.mark.parametrize(
    ("evidence", "found"),
    [
        ("Rs. 25,00 Per Month", True),  # exact substring
        ("Rs.  25,00\tPer   Month", True),  # extra spaces and tabs
        ("Joining Location : Bengaluru", True),  # the text has the extra spaces
        ("30th Sept'2026 by 9.00 AM", True),  # straight quote vs curly in text
        ("Rs. 5.00 -Rs. 8.00 LPA", True),  # hyphen vs en dash in text
        ("Per Month CTC : Rs. 5.00", True),  # spans a line break
        ("Rs. 25,000 Per Month", False),  # value altered
        ("A monthly stipend of Rs. 25,00", False),  # paraphrase
        ("rs. 25,00 per month", False),  # case is not normalized
        ("Rs. 25,00 Month", False),  # dropped word
        ("", False),
        ("   ", False),
        (None, False),
    ],
)
def test_evidence_found(evidence, found):
    assert evidence_found(evidence, TEXT) is found


def test_normalize_for_match_folds_quotes_dashes_and_spaces():
    assert normalize_for_match(" “a” — ‘b’\n\n c – d ") == "\"a\" - 'b' c - d"


@pytest.mark.parametrize(
    ("value", "evidence", "flag"),
    [
        (None, None, "missing"),
        ("", "  ", "missing"),
        ("Rs. 25,00 Per Month", "Rs. 25,00 Per Month", "none"),
        ("Rs. 25,000", "Rs. 25,000 per month", "unverified"),  # invented quote
        ("Bengaluru", None, "unverified"),  # a value with no quote is not trusted
    ],
)
def test_check_mention(value, evidence, flag):
    assert check_mention(value, evidence, TEXT) == flag
