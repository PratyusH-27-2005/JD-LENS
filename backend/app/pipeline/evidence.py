"""Step 4: is the model's quote really in the posting?

Deliberately strict. Only whitespace, quote characters and dash characters are folded;
case, punctuation and words must match. Loosening this to fuzzy matching would let a
paraphrase through, which defeats the point of asking for evidence.
"""

import re

from app.pipeline.normalize.result import Flag

_FOLD = str.maketrans(
    {
        "‘": "'",  # ‘
        "’": "'",  # ’
        "‚": "'",  # ‚
        "‛": "'",  # ‛
        "′": "'",  # ′
        "“": '"',  # “
        "”": '"',  # ”
        "„": '"',  # „
        "″": '"',  # ″
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        "―": "-",  # horizontal bar
        "−": "-",  # minus sign
    }
)
_WHITESPACE = re.compile(r"\s+")


def normalize_for_match(s: str) -> str:
    """Fold quotes and dashes to ASCII and collapse runs of whitespace to one space."""
    return _WHITESPACE.sub(" ", s.translate(_FOLD)).strip()


def evidence_found(evidence: str | None, text: str) -> bool:
    if evidence is None:
        return False
    needle = normalize_for_match(evidence)
    return bool(needle) and needle in normalize_for_match(text)


def check_mention(value: str | None, evidence: str | None, text: str) -> Flag:
    """missing if the model said nothing, none if the quote checks out, else unverified."""
    if _blank(value) and _blank(evidence):
        return "missing"
    return "none" if evidence_found(evidence, text) else "unverified"


def _blank(s: str | None) -> bool:
    return s is None or not s.strip()
