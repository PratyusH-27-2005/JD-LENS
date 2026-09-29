"""Work mode parsing. Pure functions, no LLM.

→ {"mode": "onsite" | "remote" | "hybrid", "days_per_week": int | None}.
Hybrid wins over office words ("Hybrid (3 days in office)"); remote plus onsite is
ambiguous. "virtual" is not treated as remote: in Indian placement notices it usually
describes the recruitment drive, not the job.
"""

import re

from app.pipeline.normalize.result import Normalized

_REMOTE = re.compile(r"\bremote\b|\bwork\s+from\s+home\b|\bwfh\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_ONSITE = re.compile(
    r"\bon-?\s?site\b|\bin-?\s?office\b|\bwork\s+from\s+office\b|\bwfo\b|\boffice-based\b", re.I
)
_DAYS = re.compile(
    r"\b(?P<d>[1-7])\s*days?\s*(?:a|per|/|in\s+a)\s*week\b"
    r"|\b(?P<o>[1-7])\s*days?\s*(?:in|at|from)\s+(?:the\s+)?office\b",
    re.I,
)


def parse_work_mode(text: str) -> Normalized:
    remote, hybrid, onsite = (bool(p.search(text)) for p in (_REMOTE, _HYBRID, _ONSITE))
    if hybrid:
        mode = "hybrid"
    elif remote and onsite:
        return Normalized.ambiguous("more than one work mode (remote and onsite)")
    elif remote:
        mode = "remote"
    elif onsite:
        mode = "onsite"
    else:
        return Normalized.ambiguous("no work mode found")
    days = _DAYS.search(text)
    return Normalized.ok(mode=mode, days_per_week=int(days["d"] or days["o"]) if days else None)
