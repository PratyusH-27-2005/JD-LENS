"""Deadline parsing. Pure functions, no LLM.

Handles ordinals (30th), short and long month names (Sept, September), '2026 and '26
years, ISO dates, DD/MM/YYYY, "9.00 AM", 24-hour times and noon. No timezone means IST
(tz_assumed); no time means end of day 23:59:59 (time_assumed). A missing year, an
impossible date, a DD/MM vs MM/DD clash, "midnight" or two different dates are flagged
ambiguous rather than guessed.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.pipeline.normalize.result import Normalized

IST = timezone(timedelta(hours=5, minutes=30), "IST")
_TIMEZONES = {"IST": IST, "UTC": UTC, "GMT": UTC}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MON = (
    r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?"
)
_YEAR = r"(?:['’‘](?P<yy>\d{2})\b|['’‘]?(?P<yyyy>20\d{2})\b)"
_ORD = r"(?:st|nd|rd|th)?"

_DATE_PATTERNS = [
    re.compile(rf"\b(?P<day>\d{{1,2}}){_ORD}\s*(?:of\s+)?{_MON}[\s,]*{_YEAR}?", re.I),
    re.compile(rf"\b{_MON}\s+(?P<day>\d{{1,2}}){_ORD}\b,?\s*{_YEAR}?", re.I),
    re.compile(r"\b(?P<yyyy>20\d{2})-(?P<m>\d{1,2})-(?P<day>\d{1,2})\b"),
    re.compile(r"\b(?P<a>\d{1,2})[/.-](?P<b>\d{1,2})[/.-](?P<yyyy>20\d{2})\b"),
]
_TIME_12H = re.compile(r"\b(?P<h>\d{1,2})(?:[.:](?P<min>\d{2}))?\s*(?P<ap>[ap])\.?\s?m\b\.?", re.I)
_TIME_24H = re.compile(r"\b(?P<h>[01]?\d|2[0-3]):(?P<min>[0-5]\d)\b")
_NOON = re.compile(r"\bnoon\b", re.I)
_MIDNIGHT = re.compile(r"\bmidnight\b", re.I)
_TZ = re.compile(r"\b(IST|UTC|GMT)\b")


class _Ambiguous(Exception):
    pass


@dataclass(frozen=True)
class _Date:
    year: int | None
    month: int
    day: int


def parse_deadline(text: str) -> Normalized:
    """→ {"iso", "tz_assumed", "time_assumed"}, or ambiguous with a reason."""
    try:
        year, month, day = _find_date(text)
        time = _find_time(text)
    except _Ambiguous as e:
        return Normalized.ambiguous(str(e))

    tz_match = _TZ.search(text)
    tz = _TIMEZONES[tz_match[1]] if tz_match else IST
    hour, minute, second = time if time else (23, 59, 59)
    try:
        dt = datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return Normalized.ambiguous(f"{day}/{month}/{year} is not a real date")
    return Normalized.ok(iso=dt.isoformat(), tz_assumed=tz_match is None, time_assumed=time is None)


def _find_date(text: str) -> tuple[int, int, int]:
    dates = {_to_date(m) for m in _non_overlapping_date_matches(text)}
    if not dates:
        raise _Ambiguous("no date found")
    if len(dates) > 1:
        raise _Ambiguous("more than one date")
    date = dates.pop()
    if date.year is None:
        raise _Ambiguous("no year stated")
    return date.year, date.month, date.day


def _non_overlapping_date_matches(text: str) -> list[re.Match[str]]:
    """All date matches from every pattern, keeping the earliest (then longest) on overlap."""
    matches = [m for p in _DATE_PATTERNS for m in p.finditer(text)]
    matches.sort(key=lambda m: (m.start(), -m.end()))
    kept: list[re.Match[str]] = []
    for m in matches:
        if not kept or m.start() >= kept[-1].end():
            kept.append(m)
    return kept


def _to_date(m: re.Match[str]) -> _Date:
    groups = m.groupdict()
    year = _year(groups.get("yy"), groups.get("yyyy"))
    if groups.get("mon"):
        return _Date(year, _MONTHS[groups["mon"].lower()[:3]], int(groups["day"]))
    if groups.get("m"):
        return _Date(year, int(groups["m"]), int(groups["day"]))
    # Numeric a/b/yyyy: Indian postings mean DD/MM, but only trust that when it's forced.
    a, b = int(groups["a"]), int(groups["b"])
    if a <= 12 and b <= 12 and a != b:
        raise _Ambiguous(f'"{m[0]}" could be day/month or month/day')
    day, month = (b, a) if b > 12 else (a, b)
    return _Date(year, month, day)


def _year(yy: str | None, yyyy: str | None) -> int | None:
    if yyyy:
        return int(yyyy)
    return 2000 + int(yy) if yy else None


def _find_time(text: str) -> tuple[int, int, int] | None:
    if _MIDNIGHT.search(text):
        raise _Ambiguous('"midnight" is ambiguous (start or end of the day?)')
    if m := _TIME_12H.search(text):
        hour, minute = int(m["h"]), int(m["min"] or 0)
        if not (1 <= hour <= 12 and minute <= 59):
            raise _Ambiguous(f'"{m[0].strip()}" is not a valid time')
        hour = hour % 12 + (12 if m["ap"].lower() == "p" else 0)
        return hour, minute, 0
    if m := _TIME_24H.search(text):
        return int(m["h"]), int(m["min"]), 0
    if _NOON.search(text):
        return 12, 0, 0
    return None
