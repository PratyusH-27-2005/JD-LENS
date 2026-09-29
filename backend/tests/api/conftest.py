"""API tests run against a real Postgres (TEST_DATABASE_URL), migrated with Alembic.

Each test starts from empty tables. The database name must end in _test, because the
tables are truncated: this refuses to run against the real database.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import get_session, make_engine
from app.deps import get_now
from app.llm.client import get_llm_client
from app.main import app
from app.pipeline.normalize.dates import IST
from app.ratelimit import limiter
from tests.pipeline.fakes import FakeLLMClient

BACKEND = Path(__file__).parents[2]
TEST_URL = get_settings().test_database_url
# Before the Kasparro deadline (30 Sep 2026 09:00 IST) and the Acme one (15 Oct 2026).
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=IST)


@pytest.fixture(scope="session")
def migrated_db() -> str:
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    if not (make_url(TEST_URL).database or "").endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must name a database ending in _test", returncode=2)
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["url"] = TEST_URL
    command.downgrade(cfg, "base")  # also proves the downgrade works
    command.upgrade(cfg, "head")
    return TEST_URL


@pytest_asyncio.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    """One pool for the whole run: a fresh TLS connection per test to a remote database
    (e.g. Neon) costs about a second each."""
    engine = make_engine(migrated_db)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE postings, extracted_fields, match_scores, llm_calls, profile "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def clock() -> dict[str, datetime]:
    """Mutable "now" for the app: tests can move time forward."""
    return {"now": NOW}


@pytest.fixture
async def api(
    db: async_sessionmaker[AsyncSession], fake_llm: FakeLLMClient, clock: dict[str, datetime]
) -> AsyncIterator[AsyncClient]:
    async def session_override() -> AsyncIterator[AsyncSession]:
        async with db() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_now] = lambda: clock["now"]
    limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
