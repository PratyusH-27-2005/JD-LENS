from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.errors import install_error_handlers
from app.ratelimit import limiter
from app.routers import health, postings, profile


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="JD Lens", version="0.1.0")
    settings = settings or get_settings()
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        # Optional, only for a domain you own, e.g. r"https://([a-z0-9-]+\.)?jdlens\.dev".
        # Never a pattern on *.vercel.app: anyone can name a project to match it.
        allow_origin_regex=settings.allowed_origin_regex or None,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(postings.router)
    app.include_router(profile.router)
    return app


app = create_app()
