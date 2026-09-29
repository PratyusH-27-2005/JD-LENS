from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env lives at the repo root; a backend/.env (if any) overrides it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://jdlens:jdlens@localhost:5432/jdlens"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_s: float = 30.0
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
