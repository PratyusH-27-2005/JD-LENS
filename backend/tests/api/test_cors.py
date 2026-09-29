"""CORS is configured from the environment: the deployed web app must be allowed, and
nothing else."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://jd-lens.vercel.app", True),
        ("https://jd-lens-git-main-manav.vercel.app", True),  # preview, via the regex
        ("https://evil.example", False),
        ("https://jd-lens.vercel.app.evil.example", False),
    ],
)
async def test_cors_allows_only_configured_origins(origin, allowed):
    app = create_app(
        Settings(
            allowed_origins="https://jd-lens.vercel.app",
            allowed_origin_regex=r"https://jd-lens(-[\w-]+)?\.vercel\.app",
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.options(
            "/postings",
            headers={"origin": origin, "access-control-request-method": "POST"},
        )
    assert (r.headers.get("access-control-allow-origin") == origin) is allowed
