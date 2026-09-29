"""Step 1: clean and hash. Same clean text → same hash → no second LLM call."""

import hashlib
import re

_SPACES = re.compile(r"[^\S\n]+")  # whitespace except newlines
_BLANK_LINES = re.compile(r"\n{3,}")


def clean(raw_text: str) -> str:
    """Collapse spaces within lines and runs of blank lines; keep line breaks so the
    posting still reads as a posting (for the model and for the evidence highlight)."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def content_hash(clean_text: str) -> str:
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
