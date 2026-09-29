from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.ratelimit import limiter
from app.routers import health, postings, profile


def create_app() -> FastAPI:
    app = FastAPI(title="JD Lens", version="0.1.0")
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(postings.router)
    app.include_router(profile.router)
    return app


app = create_app()
