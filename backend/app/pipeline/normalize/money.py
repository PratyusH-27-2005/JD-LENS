"""Money parsing for stipend and CTC mentions. Pure functions, no LLM.

Rules (docs/DESIGN.md, "Money parser rules"):
- Currency markers: Rs, Rs., INR, ₹, or none.
- Digit grouping must be valid Indian (1,00,000) or Western (100,000); anything else is
  ambiguous, never "fixed".
- LPA / lakh ×1,00,000, k ×1,000, crore ×1,00,00,000. LPA or per annum → yearly;
  per month or /month → monthly.
- Ranges joined by -, –, — or "to"; a unit on either end applies to both.
- ESOP / equity / stock / RSU → has_equity; cash and total are kept apart.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.pipeline.normalize.result import Normalized

Period = Literal["month", "year"]

_AMOUNT = re.compile(
    r"(?P<cur>₹|\bRs\b\.?|\bINR\b)?\s*"
    r"(?<![\d,])(?P<num>\d+(?:,\d+)*(?:\.\d+)?)"
    r"(?:\s*(?P<unit>lpa|lakhs?|lacs?|l|k|crores?|cr)\b)?",
    re.IGNORECASE,
)
_RANGE_SEP = re.compile(r"\s*(?:-|–|—|to)\s*", re.IGNORECASE)
_PER_AFTER = re.compile(r"\s*(?:/|per\b)", re.IGNORECASE)
_YEARLY = re.compile(
    r"\blpa\b|per\s+annum|\bp\.a\.|per\s+year|/\s*(?:year|yr|annum)\b|\bannually\b|\byearly\b",
    re.IGNORECASE,
)
_MONTHLY = re.compile(r"per\s+month|/\s*(?:month|mo)\b|\bmonthly\b", re.IGNORECASE)
_EQUITY = re.compile(r"\b(?:esops?|equity|stocks?|rsus?)\b", re.IGNORECASE)
_TOTAL = re.compile(r"\b(?:total|overall)\b", re.IGNORECASE)

_WESTERN = re.compile(r"\d{1,3}(?:,\d{3})+")
_INDIAN = re.compile(r"\d{1,2}(?:,\d{2})*,\d{3}")

_MULTIPLIER = {
    "lpa": 100_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "l": 100_000,
    "k": 1_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
}


class _Ambiguous(Exception):
    """Raised inside this module; public functions turn it into Normalized.ambiguous."""


@dataclass(frozen=True)
class _Money:
    """One amount or range found in the text, in rupees, before any period conversion."""

    start: int
    end: int
    low: int
    high: int


def is_valid_grouping(integer: str) -> bool:
    """True for plain digits, Western (100,000) or Indian (1,00,000) grouping."""
    if "," not in integer:
        return True
    return bool(_WESTERN.fullmatch(integer) or _INDIAN.fullmatch(integer))


def parse_stipend(text: str) -> Normalized:
    """One amount or range with a stated period → {"period", "min_inr", "max_inr"}."""
    try:
        items = _find_money(text)
        if not items:
            raise _Ambiguous("no amount found")
        if len(items) > 1:
            raise _Ambiguous(f"{len(items)} separate amounts; expected one amount or range")
        period = _period(text)
        if period is None:
            raise _Ambiguous("no pay period (per month / per annum) stated")
    except _Ambiguous as e:
        return Normalized.ambiguous(str(e))
    return Normalized.ok(period=period, min_inr=items[0].low, max_inr=items[0].high)


def parse_ctc(text: str) -> Normalized:
    """Yearly cash and total ranges, kept apart, plus whether equity is mentioned.

    CTC is annual by definition, so no period means yearly; a monthly figure is ×12.
    An amount preceded by "total"/"overall" is the total; any other amount is cash.
    Equity is never counted as cash: with equity and no stated total, total is unknown.
    """
    try:
        items = _find_money(text)
        if not items:
            raise _Ambiguous("no amount found")
        factor = 12 if _period(text) == "month" else 1
        cash, total = _split_cash_total(text, items)
    except _Ambiguous as e:
        return Normalized.ambiguous(str(e))

    has_equity = bool(_EQUITY.search(text))
    if cash is None and not has_equity:
        cash = total
    if total is None and not has_equity:
        total = cash
    return Normalized.ok(
        cash_min_inr=cash.low * factor if cash else None,
        cash_max_inr=cash.high * factor if cash else None,
        total_min_inr=total.low * factor if total else None,
        total_max_inr=total.high * factor if total else None,
        has_equity=has_equity,
    )


def reconcile(results: Sequence[Normalized]) -> list[Normalized]:
    """Several mentions of one money field must agree. If not, every mention becomes a
    conflict and all are kept: we show the disagreement instead of picking a winner.

    Pass only mentions whose evidence was verified.
    """
    if len(results) < 2 or all(r == results[0] for r in results):
        return list(results)
    reason = "mentions disagree: " + "; ".join(
        f"#{i} {_describe(r)}" for i, r in enumerate(results, start=1)
    )
    return [replace(r, flag="conflict", reason=reason) for r in results]


# --- helpers ------------------------------------------------------------------


def _find_money(text: str) -> list[_Money]:
    """Every amount or range in the text that looks like money, in order."""
    raw = list(_AMOUNT.finditer(text))
    items: list[_Money] = []
    i = 0
    while i < len(raw):
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        if nxt and _RANGE_SEP.fullmatch(text, raw[i].end(), nxt.start()):
            group = [raw[i], nxt]
            i += 2
        else:
            group = [raw[i]]
            i += 1
        if any(_looks_like_money(m, text) for m in group):
            items.append(_build(group))
    return items


def _looks_like_money(m: re.Match[str], text: str) -> bool:
    """A bare number ("3 months") is not money; a currency, unit, comma or "/…" makes it so."""
    return bool(m["cur"] or m["unit"] or "," in m["num"] or _PER_AFTER.match(text, m.end()))


def _build(group: list[re.Match[str]]) -> _Money:
    multipliers = {_MULTIPLIER[m["unit"].lower()] for m in group if m["unit"]}
    if len(multipliers) > 1:
        raise _Ambiguous("range ends use different units")
    mult = multipliers.pop() if multipliers else 1
    low = _to_inr(group[0]["num"], mult)
    high = _to_inr(group[-1]["num"], mult)
    if low > high:
        raise _Ambiguous(f"range low end is above the high end ({low} > {high})")
    return _Money(start=group[0].start(), end=group[-1].end(), low=low, high=high)


def _to_inr(num: str, multiplier: int) -> int:
    integer = num.split(".")[0]
    if not is_valid_grouping(integer):
        raise _Ambiguous(f'"{num}" is not a valid digit grouping')
    value = Decimal(num.replace(",", "")) * multiplier
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _period(text: str) -> Period | None:
    yearly, monthly = bool(_YEARLY.search(text)), bool(_MONTHLY.search(text))
    if yearly and monthly:
        raise _Ambiguous("mentions both a monthly and a yearly period")
    if yearly:
        return "year"
    return "month" if monthly else None


def _split_cash_total(text: str, items: list[_Money]) -> tuple[_Money | None, _Money | None]:
    cash: list[_Money] = []
    total: list[_Money] = []
    prev_end = 0
    for item in items:
        label = text[prev_end : item.start]
        (total if _TOTAL.search(label) else cash).append(item)
        prev_end = item.end
    if len(cash) > 1:
        raise _Ambiguous(f"more than one cash amount ({len(cash)})")
    if len(total) > 1:
        raise _Ambiguous(f"more than one total amount ({len(total)})")
    return (cash[0] if cash else None), (total[0] if total else None)


def _describe(r: Normalized) -> str:
    if r.value is None:
        return f"{r.flag} ({r.reason})"
    return ", ".join(f"{k}={v}" for k, v in r.value.items())
