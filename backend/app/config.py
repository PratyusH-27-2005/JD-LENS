from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def to_async_url(url: str) -> str:
    """Accept the plain Postgres URL that Neon/Render/Railway hand out and turn it into one
    SQLAlchemy + asyncpg understand: postgresql+asyncpg://, sslmode → ssl, and drop
    channel_binding (a libpq-only option asyncpg rejects)."""
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    if scheme != "postgresql+asyncpg":
        return url
    params = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            params.append(("ssl", value))
        elif key != "channel_binding":
            params.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


class Settings(BaseSettings):
    # .env lives at the repo root; a backend/.env (if any) overrides it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://jdlens:jdlens@localhost:5432/jdlens"
    # Only the API tests use this. They TRUNCATE tables, so it must be a separate database.
    test_database_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_s: float = 30.0
    allowed_origins: str = "http://localhost:3000"
    allowed_origin_regex: str = ""
    rate_limit_postings: str = "10/minute"
    rate_limit_resume: str = "5/minute"
    # True only when every request arrives through Cloudflare (e.g. on Render), which sets
    # CF-Connecting-IP itself. Anywhere else the header could be forged. See ratelimit.py.
    trust_cf_connecting_ip: bool = False

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        return to_async_url(v)

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
