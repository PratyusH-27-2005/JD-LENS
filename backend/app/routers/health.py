from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import db_ping

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    db: Literal["ok", "error"]
    llm_configured: bool


@router.get("/health", response_model=HealthResponse)
async def health(
    response: Response,
    db_ok: Annotated[bool, Depends(db_ping)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    # 503 when the DB is down, so the host's health check notices.
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(db="ok" if db_ok else "error", llm_configured=settings.llm_configured)
