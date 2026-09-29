import pytest
from httpx import AsyncClient

from app.config import Settings, get_settings
from app.db import db_ping
from app.main import app


@pytest.mark.parametrize(
    ("db_ok", "api_key", "status", "body"),
    [
        (True, "k", 200, {"db": "ok", "llm_configured": True}),
        (True, "", 200, {"db": "ok", "llm_configured": False}),
        (False, "k", 503, {"db": "error", "llm_configured": True}),
    ],
)
async def test_health(
    client: AsyncClient, db_ok: bool, api_key: str, status: int, body: dict
) -> None:
    async def fake_ping() -> bool:
        return db_ok

    app.dependency_overrides[db_ping] = fake_ping
    app.dependency_overrides[get_settings] = lambda: Settings(llm_api_key=api_key)

    r = await client.get("/health")

    assert r.status_code == status
    assert r.json() == body
