from datetime import UTC, datetime


def get_now() -> datetime:
    """The request's "now". A dependency so tests can pin it (deadlines, Closed badge)."""
    return datetime.now(UTC)
