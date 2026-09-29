import pytest

from app.config import to_async_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (  # Neon's copy-paste string
            "postgresql://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb"
            "?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?ssl=require",
        ),
        (  # Render / Heroku style
            "postgres://u:p@host:5432/db",
            "postgresql+asyncpg://u:p@host:5432/db",
        ),
        (  # already async: unchanged
            "postgresql+asyncpg://jdlens:jdlens@localhost:5432/jdlens",
            "postgresql+asyncpg://jdlens:jdlens@localhost:5432/jdlens",
        ),
        (  # other params survive
            "postgresql://u:p@h/db?sslmode=verify-full&application_name=jd",
            "postgresql+asyncpg://u:p@h/db?ssl=verify-full&application_name=jd",
        ),
        ("", ""),
        ("sqlite+aiosqlite:///x.db", "sqlite+aiosqlite:///x.db"),
    ],
)
def test_to_async_url(url, expected):
    assert to_async_url(url) == expected
