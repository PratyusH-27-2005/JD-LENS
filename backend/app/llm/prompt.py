"""Loads and fills versioned prompt templates. No SDK import."""

from functools import cache
from pathlib import Path

PROMPT_VERSION = "extract_v1"
RESUME_PROMPT_VERSION = "resume_v1"
_PROMPTS_DIR = Path(__file__).parent / "prompts"


@cache
def _template(version: str) -> str:
    return (_PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8")


def _retry_note(previous_error: str | None) -> str:
    if not previous_error:
        return ""
    return (
        "\nYour previous answer was rejected by the validator with this error:\n"
        f"{previous_error}\nReturn corrected JSON that matches the schema exactly.\n"
    )


def render_extract_prompt(clean_text: str, previous_error: str | None = None) -> str:
    # Fill the posting last, so text inside the posting is never treated as a placeholder.
    return (
        _template(PROMPT_VERSION)
        .replace("{retry_note}", _retry_note(previous_error))
        .replace("{clean_text}", clean_text)
    )


def render_resume_prompt(text: str, previous_error: str | None = None) -> str:
    return (
        _template(RESUME_PROMPT_VERSION)
        .replace("{retry_note}", _retry_note(previous_error))
        .replace("{text}", text)
    )
