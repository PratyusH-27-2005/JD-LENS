from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def make_engine(url: str, **kwargs: Any) -> AsyncEngine:
    # 10 s connect timeout: long enough for a Neon compute waking from scale-to-zero,
    # short enough that /health never hangs.
    return create_async_engine(url, pool_pre_ping=True, connect_args={"timeout": 10}, **kwargs)


engine = make_engine(get_settings().database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def db_ping() -> bool:
    """True if the database answers SELECT 1."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
