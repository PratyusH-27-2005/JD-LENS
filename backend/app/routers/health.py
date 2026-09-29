from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.config import Settings, get_settings
from app.db import db_ping
from app.schemas.api import HealthResponse

router = APIRouter(tags=["health"])


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
