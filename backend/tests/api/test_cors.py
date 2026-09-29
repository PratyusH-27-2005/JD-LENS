"""CORS is configured from the environment: the deployed web app must be allowed, and
nothing else. Exact URLs for *.vercel.app; a regex only on a domain we own."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://jd-lens-ten.vercel.app", True),  # exact production URL
        ("https://preview.jdlens.dev", True),  # our own domain, via the regex
        ("https://jdlens.dev", True),
        ("https://jd-lens.vercel.app", False),  # someone else's project
        ("https://jd-lens-ten-pratyush-shrivastava.vercel.app", False),
        ("https://jd-lens-ten.vercel.app.evil.example", False),
        ("https://jdlens.dev.evil.example", False),
        ("https://evil.example", False),
    ],
)
async def test_cors_allows_only_configured_origins(origin, allowed):
    app = create_app(
        Settings(
            allowed_origins="https://jd-lens-ten.vercel.app",
            allowed_origin_regex=r"https://([a-z0-9-]+\.)?jdlens\.dev",
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.options(
            "/postings",
            headers={"origin": origin, "access-control-request-method": "POST"},
        )
    assert (r.headers.get("access-control-allow-origin") == origin) is allowed
