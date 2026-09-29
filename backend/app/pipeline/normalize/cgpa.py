"""A candidate's own CGPA, parsed from a verified resume quote. Pure functions, no LLM.

→ {"cgpa": float}. Only a 10-point scale is accepted: "3.7/4" or a percentage is
flagged, not converted, because conversion formulas differ between universities.
"""

import re

from app.pipeline.normalize.result import Normalized

_NUM = r"(?P<n>\d{1,2}(?:\.\d{1,2})?)"
_SCALE = r"(?:\s*/\s*(?P<scale>\d{1,3}(?:\.\d+)?))?"
_WORD = r"(?:c\.?g\.?p\.?a|cpi|s?gpa)"
_PATTERNS = [
    # "CGPA: 8.1/10", "CGPA of 8.10", "CPI - 9.0"
    re.compile(rf"\b{_WORD}\b\s*(?:[:\-–]|of|is)?\s*{_NUM}\b{_SCALE}", re.I),
    # "8.1 CGPA", "8.1/10 CGPA"
    re.compile(rf"\b{_NUM}{_SCALE}\s*{_WORD}\b", re.I),
    # A bare "8.1/10" with no keyword
    re.compile(rf"(?<![\d.]){_NUM}\s*/\s*(?P<scale>10(?:\.0+)?)\b"),
]


def parse_cgpa(text: str) -> Normalized:
    found: set[tuple[float, float | None]] = set()
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            scale = m.groupdict().get("scale")
            found.add((float(m["n"]), float(scale) if scale else None))
    if not found:
        return Normalized.ambiguous("no CGPA found in the quote")
    values = {v for v, _ in found}
    if len(values) > 1:
        listed = ", ".join(f"{v:g}" for v in sorted(values))
        return Normalized.ambiguous(f"more than one CGPA in the quote: {listed}")
    value = values.pop()
    scales = {s for _, s in found if s is not None}
    if scales and scales != {10.0}:
        return Normalized.ambiguous(f"not on a 10-point scale (out of {max(scales):g})")
    if value > 10:
        return Normalized.ambiguous(f"{value:g} is above 10")
    return Normalized.ok(cgpa=value)
