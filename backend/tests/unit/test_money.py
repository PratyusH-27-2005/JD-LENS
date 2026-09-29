import pytest

from app.pipeline.normalize.money import is_valid_grouping, parse_ctc, parse_stipend, reconcile
from app.pipeline.normalize.result import Normalized

KASPARRO_CTC = (
    "Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant of matching value. "
    "Total Rs. 10.00–Rs. 16.00 LPA"
)


@pytest.mark.parametrize(
    ("digits", "valid"),
    [
        ("25000", True),
        ("25,000", True),
        ("100,000", True),  # Western
        ("1,000,000", True),
        ("1,00,000", True),  # Indian
        ("10,00,000", True),
        ("12,34,567", True),
        ("25,00", False),
        ("1,0000", False),
        ("1,00,00", False),
        ("123,45,678", False),
    ],
)
def test_is_valid_grouping(digits, valid):
    assert is_valid_grouping(digits) is valid


@pytest.mark.parametrize(
    ("text", "period", "lo", "hi"),
    [
        ("₹ 25,000/month stipend", "month", 25_000, 25_000),
        ("Rs. 25,000 Per Month", "month", 25_000, 25_000),
        ("INR 15,000 - 20,000 per month", "month", 15_000, 20_000),
        ("Rs 30000 per month", "month", 30_000, 30_000),
        ("₹25k/month", "month", 25_000, 25_000),
        ("₹ 20,000 to ₹ 30,000 monthly", "month", 20_000, 30_000),
        ("1,00,000 per annum", "year", 100_000, 100_000),
    ],
)
def test_parse_stipend_ok(text, period, lo, hi):
    assert parse_stipend(text) == Normalized(value={"period": period, "min_inr": lo, "max_inr": hi})


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("Rs. 25,00 Per Month", '"25,00" is not a valid digit grouping'),
        ("₹ 25,000", "no pay period"),
        ("Unpaid", "no amount found"),
        ("₹20,000/month for 3 months, then ₹25,000/month", "2 separate amounts"),
        ("₹ 1,20,000 per annum, paid monthly", "both a monthly and a yearly"),
        ("₹ 30,000 - 20,000 per month", "low end is above the high end"),
    ],
)
def test_parse_stipend_ambiguous(text, reason_part):
    result = parse_stipend(text)
    assert result.flag == "ambiguous"
    assert result.value is None
    assert reason_part in result.reason


@pytest.mark.parametrize(
    ("text", "cash", "total", "equity"),
    [
        (
            "Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant",
            (500_000, 800_000),
            (None, None),
            True,
        ),
        (KASPARRO_CTC, (500_000, 800_000), (1_000_000, 1_600_000), True),
        ("12 LPA", (1_200_000, 1_200_000), (1_200_000, 1_200_000), False),
        ("₹ 8,00,000 per annum", (800_000, 800_000), (800_000, 800_000), False),
        ("6-10 LPA + stock options", (600_000, 1_000_000), (None, None), True),
        ("Rs 50,000 per month", (600_000, 600_000), (600_000, 600_000), False),
        ("Total CTC: ₹ 18 LPA including RSUs", (None, None), (1_800_000, 1_800_000), True),
    ],
)
def test_parse_ctc_ok(text, cash, total, equity):
    assert parse_ctc(text) == Normalized(
        value={
            "cash_min_inr": cash[0],
            "cash_max_inr": cash[1],
            "total_min_inr": total[0],
            "total_max_inr": total[1],
            "has_equity": equity,
        }
    )


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("Competitive", "no amount found"),
        ("₹ 6 LPA, ₹ 8 LPA or ₹ 10 LPA depending on level", "more than one cash amount"),
        ("Rs. 5,00 LPA", '"5,00" is not a valid digit grouping'),
    ],
)
def test_parse_ctc_ambiguous(text, reason_part):
    result = parse_ctc(text)
    assert result.flag == "ambiguous"
    assert reason_part in result.reason


def test_reconcile_agreeing_mentions_unchanged():
    a = parse_stipend("₹ 25,000/month")
    b = parse_stipend("Rs. 25,000 per month")
    assert reconcile([a, b]) == [a, b]


def test_reconcile_invalid_vs_valid_is_conflict_and_keeps_both():
    # The Kasparro notice says "Rs. 25,00"; the JD says ₹ 25,000.
    notice = parse_stipend("Rs. 25,00 Per Month")
    jd = parse_stipend("₹ 25,000 per month")
    out = reconcile([notice, jd])
    assert [r.flag for r in out] == ["conflict", "conflict"]
    assert out[1].value == jd.value
    assert "25,00" in out[0].reason


def test_reconcile_different_amounts_conflict():
    out = reconcile([parse_stipend("₹ 20,000/month"), parse_stipend("₹ 25,000/month")])
    assert {r.flag for r in out} == {"conflict"}


def test_reconcile_single_or_identical_mentions_unchanged():
    bad = parse_stipend("Rs. 25,00 Per Month")
    assert reconcile([bad]) == [bad]
    assert reconcile([bad, bad]) == [bad, bad]
    assert reconcile([]) == []
