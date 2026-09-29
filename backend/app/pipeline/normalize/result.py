from dataclasses import dataclass
from typing import Any, Literal, Self

# Stored in extracted_fields.flag.
Flag = Literal["none", "ambiguous", "conflict", "unverified", "missing"]


@dataclass(frozen=True)
class Normalized:
    """What every normalizer returns: a clean value, or no value plus a flag and a reason.

    A normalizer never guesses. If the text does not parse cleanly the value is None
    and the reason says why, so the UI can show it in red.
    """

    value: dict[str, Any] | None
    flag: Flag = "none"
    reason: str | None = None

    @classmethod
    def ok(cls, **value: Any) -> Self:
        return cls(value=value)

    @classmethod
    def ambiguous(cls, reason: str) -> Self:
        return cls(value=None, flag="ambiguous", reason=reason)
