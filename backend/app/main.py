from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="JD Lens", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
