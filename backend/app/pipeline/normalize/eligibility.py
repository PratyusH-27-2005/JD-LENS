"""Eligibility parsing: CGPA cutoff and backlog rule. Pure functions, no LLM.

→ {"cgpa_min": float | None, "backlogs_allowed": bool | None}. None means the posting
doesn't say; the eligibility gate treats that as unknown ("Check manually").
"""

import re

from app.pipeline.normalize.result import Normalized

_NUM = r"(?P<n>\d{1,2}(?:\.\d{1,2})?)"
_CGPA = r"(?:c\.?g\.?p\.?a|cpi|s?gpa)"
_CGPA_PATTERNS = [
    # "6.00 or above CGPA", "7+ CGPA"
    re.compile(rf"\b{_NUM}\s*\+?\s*(?:(?:or|and|&)\s+(?:above|more|higher)\s+)?{_CGPA}\b", re.I),
    # "CGPA of 7.5", "CGPA >= 8", "Minimum CGPA: 6.5"
    re.compile(
        rf"\b{_CGPA}\b\s*(?:(?:of|is|:|>=|≥|>|above|minimum|min\.?|at\s+least|\()\s*)*{_NUM}",
        re.I,
    ),
]
_NO_BACKLOGS = re.compile(
    r"\b(?:no|zero|nil|without(?:\s+any)?)\s+(?:active\s+|live\s+|current\s+|standing\s+"
    r"|pending\s+)?backlogs?\b|\bbacklogs?\s+(?:are\s+|is\s+)?not\s+allowed",
    re.I,
)
_BACKLOGS_OK = re.compile(
    r"\bbacklogs?\s+(?:are\s+|is\s+)?allowed|\b(?:max(?:imum)?\.?|up\s*to)\s+\d+\s+(?:\w+\s+)?backlogs?\b",
    re.I,
)


class _Ambiguous(Exception):
    pass


def parse_eligibility(text: str) -> Normalized:
    try:
        cgpa_min = _cgpa_min(text)
        backlogs_allowed = _backlogs_allowed(text)
    except _Ambiguous as e:
        return Normalized.ambiguous(str(e))
    if cgpa_min is None and backlogs_allowed is None:
        return Normalized.ambiguous("no CGPA or backlog rule found")
    return Normalized.ok(cgpa_min=cgpa_min, backlogs_allowed=backlogs_allowed)


def _cgpa_min(text: str) -> float | None:
    values = sorted({float(m["n"]) for p in _CGPA_PATTERNS for m in p.finditer(text)})
    if not values:
        return None
    if len(values) > 1:
        raise _Ambiguous(f"more than one CGPA cutoff: {', '.join(map(str, values))}")
    if values[0] > 10:
        raise _Ambiguous(f"CGPA cutoff {values[0]:g} is above 10")
    return values[0]


def _backlogs_allowed(text: str) -> bool | None:
    forbids, allows = bool(_NO_BACKLOGS.search(text)), bool(_BACKLOGS_OK.search(text))
    if forbids and allows:
        raise _Ambiguous("text both allows and forbids backlogs")
    if forbids:
        return False
    return True if allows else None
